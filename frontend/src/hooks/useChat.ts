"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { useAuth } from "@/components/auth-provider"
import type { ChatMessage, AgentStep, ToolUsage, Usage, SSEEvent } from "@/types/chat"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const DEFAULT_SUGGESTIONS = [
  "Покажи статистику по NQ",
  "Найди лучшие точки входа для лонга",
  "Какая волатильность по часам?",
  "Сделай бэктест на 9:30 шорт",
]

function stripSuggestions(text: string): string {
  return text.replace(/\[SUGGESTIONS\][\s\S]*?\[\/SUGGESTIONS\]/g, "").trim()
}

function tracesToAgentSteps(traces: any[]): AgentStep[] {
  if (!traces || traces.length === 0) return []

  const agentMessages: Record<string, string> = {
    // v2 agents
    understander: "Understanding question...",
    data_fetcher: "Fetching data...",
    analyst: "Analyzing data...",
    validator: "Validating response...",
    // legacy (for old logs)
    router: "Determining question type...",
    data_agent: "Fetching data...",
    educator: "Preparing explanation...",
  }

  return traces.map((trace) => {
    const outputData =
      typeof trace.output_data === "string"
        ? JSON.parse(trace.output_data)
        : trace.output_data

    const step: AgentStep = {
      agent: trace.agent_name,
      message: agentMessages[trace.agent_name] || trace.agent_name,
      status: "completed",
      result: outputData,
      durationMs: trace.duration_ms,
      tools: [],
    }

    if (outputData?.tool_calls && Array.isArray(outputData.tool_calls)) {
      step.tools = outputData.tool_calls.map((tc: any) => ({
        name: tc.tool,
        input: tc.args,
        status: "completed" as const,
      }))
    }

    if (trace.sql_query) {
      step.tools = [
        ...(step.tools || []),
        {
          name: "SQL Query",
          input: { query: trace.sql_query },
          result: { rows: trace.sql_rows_returned, data: trace.sql_result },
          duration_ms: trace.duration_ms,
          status: "completed" as const,
        },
      ]
    }

    return step
  })
}

type UseChatOptions = {
  chatId: string | null
  onChatCreated?: (chatId: string) => void
}

export function useChat({ chatId, onChatCreated }: UseChatOptions) {
  const { session } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>([])
  const [streamingText, setStreamingText] = useState("")
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Load messages when chatId changes
  useEffect(() => {
    if (!session?.access_token) return

    // Clear messages when switching chats
    setMessages([])
    setSuggestions(DEFAULT_SUGGESTIONS)

    if (!chatId) return

    const loadChatMessages = async () => {
      try {
        const response = await fetch(`${API_URL}/chats/${chatId}/messages`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        })
        if (response.ok) {
          const data = await response.json()
          const loadedMessages: ChatMessage[] = data.messages
            .map((item: any) => [
              { role: "user" as const, content: item.question },
              {
                role: "assistant" as const,
                content: item.response,
                tools_used: [],
                agent_steps: tracesToAgentSteps(item.traces || []),
                route: item.route,
                validation_passed: item.validation_passed,
                usage: {
                  input_tokens: item.input_tokens,
                  output_tokens: item.output_tokens,
                  thinking_tokens: item.thinking_tokens,
                  cost: parseFloat(item.cost_usd) || 0,
                },
              },
            ])
            .flat()
          setMessages(loadedMessages)
        }
      } catch (e) {
        console.error("Failed to load chat messages:", e)
      }
    }

    loadChatMessages()
  }, [session?.access_token, chatId])

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return

      setMessages((prev) => [...prev, { role: "user", content: text }])
      setIsLoading(true)
      setCurrentSteps([])
      setStreamingText("")

      abortControllerRef.current = new AbortController()

      try {
        const response = await fetch(`${API_URL}/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(session?.access_token && {
              Authorization: `Bearer ${session.access_token}`,
            }),
          },
          body: JSON.stringify({
            message: text,
            chat_id: chatId,
          }),
          signal: abortControllerRef.current.signal,
        })

        if (!response.body) throw new Error("No response body")

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""
        const stepsCollected: AgentStep[] = []
        let currentAgentName: string | null = null
        let finalText = ""
        let usageData: Usage | undefined
        let route: string | undefined
        let validationPassed: boolean | undefined

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() || ""

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const event = JSON.parse(line.slice(6)) as SSEEvent

                if (event.type === "step_start") {
                  currentAgentName = event.agent
                  const newStep: AgentStep = {
                    agent: event.agent,
                    message: event.message,
                    status: "running",
                    tools: [],
                  }
                  stepsCollected.push(newStep)
                  setCurrentSteps((prev) => [...prev, newStep])
                } else if (event.type === "step_end") {
                  // v2: understander returns type as route
                  if (event.agent === "understander" || event.agent === "router") {
                    route = (event.result?.type || event.result?.route) as string | undefined
                  }
                  const stepIndex = stepsCollected.findIndex(
                    (s) => s.agent === event.agent && s.status === "running"
                  )
                  if (stepIndex >= 0) {
                    stepsCollected[stepIndex] = {
                      ...stepsCollected[stepIndex],
                      status: "completed",
                      result: event.result,
                      durationMs: event.duration_ms,
                    }
                  }
                  setCurrentSteps((prev) =>
                    prev.map((s) =>
                      s.agent === event.agent && s.status === "running"
                        ? { ...s, status: "completed", result: event.result, durationMs: event.duration_ms }
                        : s
                    )
                  )
                } else if (event.type === "tool_call") {
                  const toolCall: ToolUsage = {
                    name: event.tool,
                    input: event.args,
                    status: "running",
                  }
                  if (currentAgentName) {
                    const stepIndex = stepsCollected.findIndex(
                      (s) => s.agent === currentAgentName && s.status === "running"
                    )
                    if (stepIndex >= 0 && stepsCollected[stepIndex].tools) {
                      stepsCollected[stepIndex].tools!.push(toolCall)
                    }
                  }
                  setCurrentSteps((prev) =>
                    prev.map((s) =>
                      s.agent === currentAgentName && s.status === "running"
                        ? { ...s, tools: [...(s.tools || []), toolCall] }
                        : s
                    )
                  )
                } else if (event.type === "sql_executed") {
                  const sqlTool: ToolUsage = {
                    name: "SQL Query",
                    input: { query: event.query },
                    result: { rows: event.rows_found, error: event.error },
                    duration_ms: event.duration_ms,
                    status: "completed",
                  }
                  if (currentAgentName) {
                    const stepIndex = stepsCollected.findIndex(
                      (s) => s.agent === currentAgentName && s.status === "running"
                    )
                    if (stepIndex >= 0 && stepsCollected[stepIndex].tools) {
                      stepsCollected[stepIndex].tools!.push(sqlTool)
                    }
                  }
                } else if (event.type === "validation") {
                  validationPassed = event.status === "ok"
                  // Reset text on rewrite to avoid concatenating multiple attempts
                  if (event.status === "rewrite") {
                    finalText = ""
                    setStreamingText("")
                  }
                } else if (event.type === "text_delta") {
                  finalText += event.content
                  setStreamingText((prev) => prev + event.content)
                } else if (event.type === "suggestions") {
                  if (event.suggestions && event.suggestions.length > 0) {
                    setSuggestions(event.suggestions)
                  }
                } else if (event.type === "usage") {
                  usageData = {
                    input_tokens: event.input_tokens,
                    output_tokens: event.output_tokens,
                    thinking_tokens: event.thinking_tokens,
                    cost: event.cost,
                  }
                } else if (event.type === "chat_id") {
                  // Backend created or resolved chat - notify parent to update state
                  if (event.chat_id && onChatCreated) {
                    onChatCreated(event.chat_id)
                  }
                } else if (event.type === "done") {
                  setMessages((prev) => [
                    ...prev,
                    {
                      role: "assistant",
                      content: stripSuggestions(finalText),
                      agent_steps: [...stepsCollected],
                      route,
                      validation_passed: validationPassed,
                      usage: usageData,
                    },
                  ])
                  setCurrentSteps([])
                  setStreamingText("")
                } else if (event.type === "error") {
                  setMessages((prev) => [
                    ...prev,
                    { role: "assistant", content: `Ошибка: ${event.message}` },
                  ])
                  setCurrentSteps([])
                }
              } catch (e) {
                console.error("Failed to parse SSE event:", e)
              }
            }
          }
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Ошибка подключения к серверу" },
        ])
        setCurrentSteps([])
        setStreamingText("")
      } finally {
        setIsLoading(false)
        abortControllerRef.current = null
      }
    },
    [isLoading, session?.access_token, chatId]
  )

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsLoading(false)
    setCurrentSteps([])
    setStreamingText("")
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "Остановлено пользователем" },
    ])
  }, [])

  return {
    messages,
    isLoading,
    currentSteps,
    streamingText,
    suggestions,
    sendMessage,
    stopGeneration,
  }
}
