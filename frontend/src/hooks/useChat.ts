"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { useAuth } from "@/providers"
import type { ChatMessage, AgentStep, ToolUsage, Usage, SSEEvent, DataCard } from "@/types/chat"

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
    // Barb architecture agents
    barb: "Understanding question...",
    data_fetcher: "Fetching data...",
    analyst: "Analyzing data...",
    validator: "Validating response...",
    // legacy (for old logs)
    understander: "Understanding question...",
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
  onTitleUpdated?: (chatId: string, title: string) => void
}

export function useChat({ chatId, onChatCreated, onTitleUpdated }: UseChatOptions) {
  const { session } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>([])
  const [streamingText, setStreamingText] = useState("")
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Load messages when chatId changes
  useEffect(() => {
    if (!session?.access_token) return

    // Reset state for new chat
    setSuggestions(DEFAULT_SUGGESTIONS)

    if (!chatId) {
      setMessages([])
      setIsLoadingHistory(false)
      return
    }

    // Start loading immediately (don't clear messages yet to avoid flash)
    setIsLoadingHistory(true)

    const loadChatMessages = async () => {
      try {
        const response = await fetch(`${API_URL}/chats/${chatId}/messages`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        })
        if (response.ok) {
          const data = await response.json()
          // API returns array directly, not {messages: [...]}
          const messages = Array.isArray(data) ? data : []
          const loadedMessages: ChatMessage[] = messages
            .map((item: any) => [
              { role: "user" as const, content: item.question },
              {
                role: "assistant" as const,
                content: item.response,
                request_id: item.request_id,
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
                feedback: item.feedback,
              },
            ])
            .flat()
          setMessages(loadedMessages)
        } else {
          // Failed to load - clear messages
          setMessages([])
        }
      } catch (e) {
        console.error("Failed to load chat messages:", e)
        setMessages([])
      } finally {
        setIsLoadingHistory(false)
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
        let previewText = ""      // Expert context before data
        let summaryText = ""      // Summary after data
        let isAfterDataReady = false
        let usageData: Usage | undefined
        let route: string | undefined
        let validationPassed: boolean | undefined
        let dataCard: DataCard | undefined
        let offerAnalysis = false

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
                  // Barb returns type as route
                  if (event.agent === "barb" || event.agent === "understander" || event.agent === "router") {
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
                    previewText = ""
                    summaryText = ""
                    isAfterDataReady = false
                    setStreamingText("")
                  }
                } else if (event.type === "text_delta") {
                  // Route text to preview or summary based on data state
                  if (!isAfterDataReady) {
                    previewText += event.content
                    setStreamingText(previewText)
                  } else {
                    summaryText += event.content
                    setStreamingText(summaryText)
                  }
                } else if (event.type === "suggestions") {
                  if (event.suggestions && event.suggestions.length > 0) {
                    setSuggestions(event.suggestions)
                  }
                } else if (event.type === "data_title") {
                  // Save data title for data card
                  dataCard = { title: event.title, row_count: 0, data: {} }
                } else if (event.type === "data_ready") {
                  // Data is ready - switch to summary mode
                  dataCard = {
                    title: dataCard?.title || "",
                    row_count: event.row_count,
                    data: event.data,
                  }
                  isAfterDataReady = true
                  // Clear streaming for summary
                  setStreamingText("")
                } else if (event.type === "offer_analysis") {
                  // Large dataset - offer analysis button
                  offerAnalysis = true
                  isAfterDataReady = true
                  // Use offer message as summary
                  summaryText = event.message
                  setStreamingText(event.message)
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
                } else if (event.type === "chat_title") {
                  // Backend generated a title for the chat
                  if (event.chat_id && event.title && onTitleUpdated) {
                    onTitleUpdated(event.chat_id, event.title)
                  }
                } else if (event.type === "done") {
                  // Determine content: summary if we got data, otherwise preview
                  const content = summaryText || previewText
                  const preview = dataCard ? previewText : undefined // Only include preview if there's a data card

                  setMessages((prev) => [
                    ...prev,
                    {
                      role: "assistant",
                      content: stripSuggestions(content),
                      preview: preview ? stripSuggestions(preview) : undefined,
                      request_id: event.request_id,
                      agent_steps: [...stepsCollected],
                      route,
                      validation_passed: validationPassed,
                      usage: usageData,
                      data_card: dataCard,
                      offer_analysis: offerAnalysis,
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

  const updateFeedback = useCallback(
    async (requestId: string, type: "positive" | "negative", text: string) => {
      if (!session?.access_token) return

      const field = type === "positive" ? "positive_feedback" : "negative_feedback"

      try {
        const response = await fetch(`${API_URL}/messages/${requestId}/feedback`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({ [field]: text }),
        })

        if (response.ok) {
          // Update local state
          setMessages((prev) =>
            prev.map((msg) =>
              msg.request_id === requestId
                ? { ...msg, feedback: { ...msg.feedback, [field]: text } }
                : msg
            )
          )
        }
      } catch (e) {
        console.error("Failed to update feedback:", e)
      }
    },
    [session?.access_token]
  )

  return {
    messages,
    isLoading,
    isLoadingHistory,
    currentSteps,
    streamingText,
    suggestions,
    sendMessage,
    stopGeneration,
    updateFeedback,
  }
}
