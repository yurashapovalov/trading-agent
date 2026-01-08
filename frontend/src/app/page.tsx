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
  result: unknown
  duration_ms: number
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
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return

    setInput("")
    setMessages((prev) => [...prev, { role: "user", content: text }])
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: text }),
      })

      const data = await response.json()
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          tools_used: data.tools_used,
        },
      ])
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Ошибка подключения к серверу" },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion)
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground py-12">
              <h2 className="text-xl font-medium mb-2">Trading Analytics</h2>
              <p className="text-sm">Задай вопрос о торговых данных NQ</p>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={index}>
              {/* Tool calls before assistant response */}
              {message.role === "assistant" && message.tools_used?.map((tool, i) => (
                <Tool key={i} className="mb-4">
                  <ToolHeader
                    title={`${tool.name} (${tool.duration_ms.toFixed(0)}ms)`}
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

          {isLoading && (
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
          <PromptInput
            onSubmit={({ text }) => sendMessage(text)}
          >
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
