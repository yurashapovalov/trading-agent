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
import { useState, useRef, useEffect } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const SUGGESTIONS = [
  "Покажи статистику по NQ",
  "Найди лучшие точки входа для лонга",
  "Какая волатильность по часам?",
  "Сделай бэктест на 9:30 шорт",
]

type ToolUsage = {
  name: string
  input: Record<string, unknown>
  result?: unknown
  duration_ms?: number
  status: "running" | "completed"
}

type ChatMessage = {
  role: "user" | "assistant"
  content: string
  tools_used?: ToolUsage[]
}

export default function Chat() {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentTools, setCurrentTools] = useState<ToolUsage[]>([])
  const [streamingText, setStreamingText] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentTools, streamingText])

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return

    setInput("")
    setMessages((prev) => [...prev, { role: "user", content: text }])
    setIsLoading(true)
    setCurrentTools([])
    setStreamingText("")

    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: text }),
      })

      if (!response.body) {
        throw new Error("No response body")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      const toolsCollected: ToolUsage[] = []
      let finalText = ""

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

              if (event.type === "tool_start") {
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
              } else if (event.type === "done") {
                // Add final message
                setMessages((prev) => [
                  ...prev,
                  {
                    role: "assistant",
                    content: finalText,
                    tools_used: toolsCollected,
                  },
                ])
                setCurrentTools([])
                setStreamingText("")
              } else if (event.type === "error") {
                setMessages((prev) => [
                  ...prev,
                  { role: "assistant", content: `Ошибка: ${event.message}` },
                ])
                setCurrentTools([])
              }
            } catch (e) {
              console.error("Failed to parse SSE event:", e)
            }
          }
        }
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Ошибка подключения к серверу" },
      ])
      setCurrentTools([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion)
  }

  const getToolState = (status: "running" | "completed") => {
    return status === "running" ? "input-available" : "output-available"
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {messages.length === 0 && currentTools.length === 0 && (
            <div className="text-center text-muted-foreground py-12">
              <h2 className="text-xl font-medium mb-2">Trading Analytics</h2>
              <p className="text-sm">Задай вопрос о торговых данных NQ</p>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={index}>
              {/* Tool calls before assistant response */}
              {message.role === "assistant" &&
                message.tools_used?.map((tool, i) => (
                  <Tool key={i} className="mb-4">
                    <ToolHeader
                      title={`${tool.name} (${tool.duration_ms?.toFixed(0)}ms)`}
                      type="tool-invocation"
                      state="output-available"
                    />
                    <ToolContent>
                      <ToolInput input={tool.input} />
                      <ToolOutput output={tool.result} errorText={undefined} />
                    </ToolContent>
                  </Tool>
                ))}

              {/* Message */}
              <Message from={message.role}>
                <MessageContent>
                  <MessageResponse>{message.content}</MessageResponse>
                </MessageContent>
              </Message>
            </div>
          ))}

          {/* Currently running tools */}
          {currentTools.length > 0 && (
            <div>
              {currentTools.map((tool, i) => (
                <Tool key={i} className="mb-4">
                  <ToolHeader
                    title={
                      tool.status === "running"
                        ? tool.name
                        : `${tool.name} (${tool.duration_ms?.toFixed(0)}ms)`
                    }
                    type="tool-invocation"
                    state={getToolState(tool.status)}
                  />
                  <ToolContent>
                    <ToolInput input={tool.input} />
                    {tool.status === "completed" && (
                      <ToolOutput output={tool.result} errorText={undefined} />
                    )}
                  </ToolContent>
                </Tool>
              ))}
            </div>
          )}

          {/* Streaming text */}
          {streamingText && (
            <Message from="assistant">
              <MessageContent>
                <MessageResponse>{streamingText}</MessageResponse>
              </MessageContent>
            </Message>
          )}

          {isLoading && currentTools.length === 0 && !streamingText && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader size={16} />
              <span className="text-sm">Думаю...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Suggestions + Input */}
      <div className="px-4 py-4 space-y-3">
        <div className="max-w-2xl mx-auto">
          {/* Suggestions */}
          {messages.length === 0 && (
            <Suggestions className="mb-3">
              {SUGGESTIONS.map((suggestion) => (
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
              placeholder="Спроси о торговых данных..."
            />
            <PromptInputFooter>
              <div />
              <PromptInputSubmit
                disabled={!input.trim() || isLoading}
                status={isLoading ? "submitted" : undefined}
              />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>
    </div>
  )
}
