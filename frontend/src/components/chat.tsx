"use client"

import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message"
import {
  Tool,
  ToolHeader,
  ToolContent,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool"
import { Loader } from "@/components/ai-elements/loader"
import { Suggestions, Suggestion } from "@/components/ai-elements/suggestion"
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputFooter,
  PromptInputSubmit,
} from "@/components/ai-elements/prompt-input"
import { Actions } from "@/components/ui/shadcn-io/ai/actions"
import { useState, useRef, useEffect } from "react"
import { useAuth } from "@/components/auth-provider"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const DEFAULT_SUGGESTIONS = [
  "Покажи статистику по NQ",
  "Найди лучшие точки входа для лонга",
  "Какая волатильность по часам?",
  "Сделай бэктест на 9:30 шорт",
]

// Strip [SUGGESTIONS] block from text
function stripSuggestions(text: string): string {
  return text.replace(/\[SUGGESTIONS\][\s\S]*?\[\/SUGGESTIONS\]/g, '').trim()
}

type ToolUsage = {
  name: string
  input: Record<string, unknown>
  result?: unknown
  duration_ms?: number
  status: "running" | "completed"
}

type AgentStep = {
  agent: string
  message: string
  status: "running" | "completed"
  result?: Record<string, unknown>
  tools?: ToolUsage[]  // Tools executed by this agent
  durationMs?: number
}

type Usage = {
  input_tokens: number
  output_tokens: number
  thinking_tokens?: number
  cost: number
}

type ChatMessage = {
  role: "user" | "assistant"
  content: string
  tools_used?: ToolUsage[]
  agent_steps?: AgentStep[]  // Full agent execution trace
  route?: string
  validation_passed?: boolean
  usage?: Usage
}

export default function Chat() {
  const { user, session, signOut } = useAuth()
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentTools, setCurrentTools] = useState<ToolUsage[]>([])
  const [currentSteps, setCurrentSteps] = useState<AgentStep[]>([])
  const [streamingText, setStreamingText] = useState("")
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Generate session ID only on client side
  const sessionIdRef = useRef<string>("")
  if (typeof window !== "undefined" && !sessionIdRef.current) {
    sessionIdRef.current = `session_${Date.now()}_${Math.random().toString(36).slice(2)}`
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentTools, currentSteps, streamingText])

  // Convert traces from API to agent_steps format
  const tracesToAgentSteps = (traces: any[]): AgentStep[] => {
    if (!traces || traces.length === 0) return []

    const agentMessages: Record<string, string> = {
      router: "Determining question type...",
      data_agent: "Fetching data...",
      analyst: "Analyzing data...",
      analyst_no_data: "Analyzing scenario...",
      educator: "Preparing explanation...",
      validator: "Validating response...",
    }

    return traces.map(trace => {
      const outputData = typeof trace.output_data === 'string'
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

      // Add tool calls from output_data (Gemini function calling)
      if (outputData?.tool_calls && Array.isArray(outputData.tool_calls)) {
        step.tools = outputData.tool_calls.map((tc: any) => ({
          name: tc.tool,
          input: tc.args,
          status: "completed" as const,
        }))
      }

      // Add SQL query as a tool if present
      if (trace.sql_query) {
        step.tools = [...(step.tools || []), {
          name: "SQL Query",
          input: { query: trace.sql_query },
          result: { rows: trace.sql_rows_returned, data: trace.sql_result },
          duration_ms: trace.duration_ms,
          status: "completed" as const,
        }]
      }

      return step
    })
  }

  // Load chat history on mount
  useEffect(() => {
    if (!session?.access_token) return

    const loadHistory = async () => {
      try {
        const response = await fetch(`${API_URL}/chat/history`, {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        })
        if (response.ok) {
          const history = await response.json()
          const loadedMessages: ChatMessage[] = history.map((item: any) => ([
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
          ])).flat()
          setMessages(loadedMessages)
        }
      } catch (e) {
        console.error("Failed to load history:", e)
      }
    }

    loadHistory()
  }, [session?.access_token])

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return

    setInput("")
    setMessages((prev) => [...prev, { role: "user", content: text }])
    setIsLoading(true)
    setCurrentTools([])
    setCurrentSteps([])
    setStreamingText("")

    // Create abort controller for this request
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access_token && { Authorization: `Bearer ${session.access_token}` }),
        },
        body: JSON.stringify({ message: text, session_id: sessionIdRef.current }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.body) {
        throw new Error("No response body")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      const toolsCollected: ToolUsage[] = []
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
              const event = JSON.parse(line.slice(6))

              // New multi-agent events
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
                if (event.agent === "router") {
                  route = event.result?.route as string | undefined
                }
                // Update the step in stepsCollected
                const stepIndex = stepsCollected.findIndex(
                  s => s.agent === event.agent && s.status === "running"
                )
                if (stepIndex >= 0) {
                  stepsCollected[stepIndex] = {
                    ...stepsCollected[stepIndex],
                    status: "completed",
                    result: event.result,
                  }
                }
                setCurrentSteps((prev) =>
                  prev.map((s) =>
                    s.agent === event.agent && s.status === "running"
                      ? { ...s, status: "completed", result: event.result }
                      : s
                  )
                )
              } else if (event.type === "tool_call") {
                // Gemini function calling - show tool call from agent
                const toolCall: ToolUsage = {
                  name: event.tool,
                  input: event.args,
                  status: "running",
                }
                // Attach to current agent's step
                if (currentAgentName) {
                  const stepIndex = stepsCollected.findIndex(
                    s => s.agent === currentAgentName && s.status === "running"
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
                // Show SQL query as a tool-like display
                const sqlTool: ToolUsage = {
                  name: "SQL Query",
                  input: { query: event.query },
                  result: { rows: event.rows_found, error: event.error },
                  duration_ms: event.duration_ms,
                  status: "completed",
                }
                toolsCollected.push(sqlTool)
                // Attach tool to current agent's step
                if (currentAgentName) {
                  const stepIndex = stepsCollected.findIndex(
                    s => s.agent === currentAgentName && s.status === "running"
                  )
                  if (stepIndex >= 0 && stepsCollected[stepIndex].tools) {
                    stepsCollected[stepIndex].tools!.push(sqlTool)
                  }
                }
                setCurrentTools((prev) => [...prev, sqlTool])
              } else if (event.type === "validation") {
                validationPassed = event.status === "ok"
              } else if (event.type === "tool_start") {
                // Legacy tool events (keep for compatibility)
                const newTool: ToolUsage = {
                  name: event.name,
                  input: event.input,
                  status: "running",
                }
                setCurrentTools((prev) => [...prev, newTool])
              } else if (event.type === "tool_end") {
                const completedTool: ToolUsage = {
                  name: event.name,
                  input: event.input,
                  result: event.result,
                  duration_ms: event.duration_ms,
                  status: "completed",
                }
                toolsCollected.push(completedTool)
                setCurrentTools((prev) =>
                  prev.map((t) =>
                    t.name === event.name && t.status === "running"
                      ? completedTool
                      : t
                  )
                )
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
              } else if (event.type === "done") {
                setMessages((prev) => [
                  ...prev,
                  {
                    role: "assistant",
                    content: stripSuggestions(finalText),
                    tools_used: toolsCollected,
                    agent_steps: [...stepsCollected], // Create new array to ensure React detects change
                    route,
                    validation_passed: validationPassed,
                    usage: usageData,
                  },
                ])
                setCurrentTools([])
                setCurrentSteps([])
                setStreamingText("")
              } else if (event.type === "error") {
                setMessages((prev) => [
                  ...prev,
                  { role: "assistant", content: `Ошибка: ${event.message}` },
                ])
                setCurrentTools([])
                setCurrentSteps([])
              }
            } catch (e) {
              console.error("Failed to parse SSE event:", e)
            }
          }
        }
      }
    } catch (error) {
      // Don't show error if it was aborted by user
      if (error instanceof Error && error.name === "AbortError") {
        return
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Ошибка подключения к серверу" },
      ])
      setCurrentTools([])
      setStreamingText("")
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsLoading(false)
    setCurrentTools([])
    setCurrentSteps([])
    setStreamingText("")
    // Add message that generation was stopped
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "Остановлено пользователем" },
    ])
  }

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion)
  }

  return (
    <div className="flex flex-col h-dvh bg-background">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-border">
        <h1 className="text-sm font-medium">Trading Analytics</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">{user?.email}</span>
          <button
            onClick={signOut}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">

          {messages.map((message, index) => (
            <div key={index}>
              {/* Agent steps - each step is a collapsible Tool */}
              {message.role === "assistant" && message.agent_steps && message.agent_steps.length > 0 && (
                <div className="space-y-2 mb-4">
                  {message.agent_steps.map((step, i) => (
                    <Tool key={i}>
                      <ToolHeader
                        title={step.message}
                        type="tool-invocation"
                        state={step.status === "running" ? "input-available" : "output-available"}
                      />
                      <ToolContent>
                        {step.result && (
                          <ToolOutput
                            output={step.result as any}
                            errorText={undefined}
                          />
                        )}
                        {step.tools && step.tools.length > 0 && step.tools.map((tool, j) => {
                          return (
                            <div key={j}>
                              <ToolInput input={tool.input as any} />
                              {tool.result ? (
                                <ToolOutput
                                  output={tool.result as any}
                                  errorText={undefined}
                                />
                              ) : null}
                            </div>
                          )
                        })}
                      </ToolContent>
                    </Tool>
                  ))}
                </div>
              )}

              {/* Message */}
              <Message from={message.role}>
                <MessageContent>
                  <MessageResponse>{message.content}</MessageResponse>
                </MessageContent>
                {message.role === "assistant" && message.usage && (
                  <Actions className="mt-2">
                    <span className="text-xs text-muted-foreground">
                      ↑{message.usage.input_tokens.toLocaleString()} · ↓{message.usage.output_tokens.toLocaleString()}{message.usage.thinking_tokens ? ` · 🧠${message.usage.thinking_tokens.toLocaleString()}` : ''} · ${message.usage.cost.toFixed(4)}
                    </span>
                  </Actions>
                )}
              </Message>
            </div>
          ))}


          {/* Agent steps progress - shown during streaming */}
          {currentSteps.length > 0 && (
            <div className="space-y-2 mb-4">
              {currentSteps.map((step, i) => (
                <Tool key={i}>
                  <ToolHeader
                    title={step.message}
                    type="tool-invocation"
                    state={step.status === "running" ? "input-available" : "output-available"}
                  />
                  <ToolContent>
                    {step.result && (
                      <ToolOutput
                        output={step.result as any}
                        errorText={undefined}
                      />
                    )}
                    {step.tools && step.tools.length > 0 && step.tools.map((tool, j) => {
                      return (
                        <div key={j}>
                          <ToolInput input={tool.input as any} />
                          {tool.result ? (
                            <ToolOutput
                              output={tool.result as any}
                              errorText={undefined}
                            />
                          ) : null}
                        </div>
                      )
                    })}
                  </ToolContent>
                </Tool>
              ))}
            </div>
          )}

          {/* Streaming text - shown after agent steps */}
          {streamingText && (
            <Message from="assistant">
              <MessageContent>
                <MessageResponse>{streamingText}</MessageResponse>
              </MessageContent>
            </Message>
          )}

          {isLoading && currentSteps.length === 0 && currentTools.length === 0 && !streamingText && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader size={16} />
              <span className="text-sm">Думаю...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Suggestions + Input */}
      <div>
        <div className="max-w-2xl mx-auto px-4 py-4 space-y-3">
          {/* Suggestions */}
          {!isLoading && suggestions.length > 0 && (
            <Suggestions className="mb-3">
              {suggestions.map((suggestion: string) => (
                <Suggestion
                  key={suggestion}
                  suggestion={suggestion}
                  onClick={handleSuggestionClick}
                />
              ))}
            </Suggestions>
          )}

          {/* Input */}
          <PromptInput onSubmit={({ text }) => sendMessage(text)}>
            <PromptInputTextarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything about NQ futures..."
            />
            <PromptInputFooter>
              <div />
              {isLoading ? (
                <button
                  type="button"
                  onClick={stopGeneration}
                  className="inline-flex items-center justify-center rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
                >
                  Stop
                </button>
              ) : (
                <PromptInputSubmit
                  disabled={!input.trim()}
                />
              )}
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>
    </div>
  )
}
