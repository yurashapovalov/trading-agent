"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { useAuth } from "@/providers"
import type { ChatMessage, AgentStep, ToolUsage, Usage, SSEEvent, DataCard } from "@/types/chat"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

function stripSuggestions(text: string): string {
  return text.replace(/\[SUGGESTIONS\][\s\S]*?\[\/SUGGESTIONS\]/g, "").trim()
}

function tracesToAgentSteps(traces: any[]): AgentStep[] {
  if (!traces || traces.length === 0) return []

  const agentMessages: Record<string, string> = {
    // Current architecture
    intent: "Classifying question...",
    understander: "Understanding context...",
    parser: "Parsing request...",
    planner: "Planning queries...",
    executor: "Executing queries...",
    presenter: "Formatting response...",
    clarifier: "Preparing clarification...",
    // Legacy (for old logs)
    barb: "Understanding question...",
    data_fetcher: "Fetching data...",
    analyst: "Analyzing data...",
    validator: "Validating response...",
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

// Extract data_card and preview from traces for history loading
function extractDataFromTraces(traces: any[], requestId?: string): { dataCard?: DataCard; preview?: string } {
  if (!traces || traces.length === 0) return {}

  let dataCard: DataCard | undefined
  let preview: string | undefined
  let dataTitle: string | undefined
  let rowCount = 0

  for (const trace of traces) {
    const outputData =
      typeof trace.output_data === "string"
        ? JSON.parse(trace.output_data)
        : trace.output_data

    if (!outputData) continue

    // Find understander trace with acknowledge (this is the preview)
    if (trace.agent_name === "understander" && outputData.acknowledge) {
      preview = outputData.acknowledge
    }

    // Find presenter trace with title and row_count
    if (trace.agent_name === "presenter") {
      if (outputData.title) {
        dataTitle = outputData.title
      }
      if (outputData.row_count !== undefined) {
        rowCount = outputData.row_count
      }
    }

    // Legacy: Find responder trace with data_title
    if (trace.agent_name === "responder" && outputData.data_title) {
      dataTitle = outputData.data_title
      preview = outputData.response
    }

    // Legacy: Find data_fetcher trace with full_data
    if (trace.agent_name === "data_fetcher" && outputData.full_data) {
      const fullData = outputData.full_data
      dataTitle = fullData.title || dataTitle
      rowCount = fullData.row_count || 0
    }

    // Find executor trace with data (for row count)
    if (trace.agent_name === "executor" && outputData.data) {
      const data = outputData.data
      if (Array.isArray(data) && data.length > 0) {
        // Sum row counts from all results
        rowCount = data.reduce((sum: number, r: any) => sum + (r.rows?.length || r.row_count || 0), 0)
      }
    }
  }

  // Create data card if we have title (data will be loaded from API on click)
  if (dataTitle) {
    dataCard = {
      title: dataTitle,
      row_count: rowCount,
      request_id: requestId,
    }
  }

  return { dataCard, preview }
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
  const [streamingPreview, setStreamingPreview] = useState("")
  const [streamingText, setStreamingText] = useState("")
  const [streamingDataCard, setStreamingDataCard] = useState<DataCard | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const skipNextHistoryLoadRef = useRef(false)

  // Load messages when chatId changes
  useEffect(() => {
    if (!session?.access_token) return

    if (!chatId) {
      setMessages([])
      setIsLoadingHistory(false)
      return
    }

    // Skip loading if chat was just created (messages already in state)
    if (skipNextHistoryLoadRef.current) {
      skipNextHistoryLoadRef.current = false
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
            .map((item: any) => {
              const traces = item.traces || []
              const { dataCard, preview } = extractDataFromTraces(traces, item.request_id)

              return [
                { role: "user" as const, content: item.question },
                {
                  role: "assistant" as const,
                  content: item.response,
                  preview: dataCard ? preview : undefined, // Only include preview if there's data
                  request_id: item.request_id,
                  tools_used: [],
                  agent_steps: tracesToAgentSteps(traces),
                  route: item.route,
                  validation_passed: item.validation_passed,
                  usage: {
                    input_tokens: item.input_tokens,
                    output_tokens: item.output_tokens,
                    thinking_tokens: item.thinking_tokens,
                    cost: parseFloat(item.cost_usd) || 0,
                  },
                  feedback: item.feedback,
                  data_card: dataCard,
                },
              ]
            })
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
      setStreamingPreview("")
      setStreamingText("")
      setStreamingDataCard(null)

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
                    setStreamingPreview("")
                    setStreamingText("")
                    setStreamingDataCard(null)
                  }
                } else if (event.type === "text_delta") {
                  // Route text to preview or summary based on data state
                  if (!isAfterDataReady) {
                    previewText += event.content
                    setStreamingPreview(previewText)
                  } else {
                    summaryText += event.content
                    setStreamingText(summaryText)
                  }
                } else if (event.type === "data_title") {
                  // Save data title for data card
                  dataCard = { title: event.title, row_count: 0 }
                  setStreamingDataCard({ title: event.title, row_count: 0 })
                } else if (event.type === "data_ready") {
                  // Data is ready - switch to summary mode
                  dataCard = {
                    title: dataCard?.title || "",
                    row_count: event.row_count,
                  }
                  setStreamingDataCard(dataCard)
                  isAfterDataReady = true
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
                    // Skip history reload - we already have messages in state
                    skipNextHistoryLoadRef.current = true
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

                  // Add request_id to dataCard for API loading
                  const finalDataCard = dataCard
                    ? { ...dataCard, request_id: event.request_id }
                    : undefined

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
                      data_card: finalDataCard,
                      offer_analysis: offerAnalysis,
                    },
                  ])
                  setCurrentSteps([])
                  setStreamingPreview("")
                  setStreamingText("")
                  setStreamingDataCard(null)
                } else if (event.type === "error") {
                  setMessages((prev) => [
                    ...prev,
                    { role: "assistant", content: `Ошибка: ${event.message}` },
                  ])
                  setCurrentSteps([])
                  setStreamingPreview("")
                  setStreamingText("")
                  setStreamingDataCard(null)
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
        setStreamingPreview("")
        setStreamingText("")
        setStreamingDataCard(null)
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
    setStreamingPreview("")
    setStreamingText("")
    setStreamingDataCard(null)
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
    streamingPreview,
    streamingText,
    streamingDataCard,
    sendMessage,
    stopGeneration,
    updateFeedback,
  }
}
