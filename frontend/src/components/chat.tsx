"use client"

import { useState } from "react"
import { useAuth } from "@/components/auth-provider"
import { useChat } from "@/hooks/useChat"

// shadcn-io/ai components
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ui/shadcn-io/ai/conversation"
import { Message, MessageContent } from "@/components/ui/shadcn-io/ai/message"
import { Response } from "@/components/ui/shadcn-io/ai/response"
import {
  Reasoning,
  ReasoningTrigger,
  ReasoningContent,
} from "@/components/ui/shadcn-io/ai/reasoning"
import { Suggestions, Suggestion } from "@/components/ui/shadcn-io/ai/suggestion"
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
  PromptInputSubmit,
} from "@/components/ui/shadcn-io/ai/prompt-input"
import { Loader } from "@/components/ui/shadcn-io/ai/loader"
import { Actions } from "@/components/ui/shadcn-io/ai/actions"

import type { AgentStep } from "@/types/chat"

function AgentSteps({ steps, isStreaming }: { steps: AgentStep[]; isStreaming?: boolean }) {
  if (steps.length === 0) return null

  // Combine all steps into one reasoning block
  const combinedContent = steps
    .map((step) => {
      let content = `**${step.message}**`
      if (step.result) {
        content += `\n\`\`\`json\n${JSON.stringify(step.result, null, 2)}\n\`\`\``
      }
      if (step.tools && step.tools.length > 0) {
        step.tools.forEach((tool) => {
          content += `\n\n*${tool.name}:*\n\`\`\`json\n${JSON.stringify(tool.input, null, 2)}\n\`\`\``
          if (tool.result) {
            content += `\n\`\`\`json\n${JSON.stringify(tool.result, null, 2)}\n\`\`\``
          }
        })
      }
      return content
    })
    .join("\n\n---\n\n")

  return (
    <Reasoning isStreaming={isStreaming} defaultOpen={isStreaming}>
      <ReasoningTrigger title={isStreaming ? "Thinking..." : `${steps.length} steps`} />
      <ReasoningContent>{combinedContent}</ReasoningContent>
    </Reasoning>
  )
}

function UsageDisplay({ usage }: { usage: { input_tokens: number; output_tokens: number; thinking_tokens?: number; cost: number } }) {
  return (
    <Actions className="mt-2">
      <span className="text-xs text-muted-foreground">
        {usage.input_tokens.toLocaleString()}
        {" / "}
        {usage.output_tokens.toLocaleString()}
        {usage.thinking_tokens ? ` / ${usage.thinking_tokens.toLocaleString()}` : ""}
        {" - $"}
        {usage.cost.toFixed(4)}
      </span>
    </Actions>
  )
}

export default function Chat() {
  const { user, signOut } = useAuth()
  const [input, setInput] = useState("")
  const {
    messages,
    isLoading,
    currentSteps,
    streamingText,
    suggestions,
    sendMessage,
    stopGeneration,
  } = useChat()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim()) {
      sendMessage(input)
      setInput("")
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion)
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

      {/* Messages with auto-scroll */}
      <Conversation className="flex-1">
        <ConversationContent className="max-w-2xl mx-auto py-6 space-y-6">
          {messages.map((message, index) => (
            <div key={index}>
              {/* Agent steps for assistant messages */}
              {message.role === "assistant" && message.agent_steps && (
                <AgentSteps steps={message.agent_steps} />
              )}

              {/* Message */}
              <Message from={message.role}>
                <MessageContent>
                  <Response>{message.content}</Response>
                </MessageContent>
              </Message>

              {/* Usage stats */}
              {message.role === "assistant" && message.usage && (
                <UsageDisplay usage={message.usage} />
              )}
            </div>
          ))}

          {/* Current streaming */}
          {currentSteps.length > 0 && (
            <AgentSteps steps={currentSteps} isStreaming />
          )}

          {streamingText && (
            <Message from="assistant">
              <MessageContent>
                <Response>{streamingText}</Response>
              </MessageContent>
            </Message>
          )}

          {isLoading && currentSteps.length === 0 && !streamingText && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader size={16} />
              <span className="text-sm">Thinking...</span>
            </div>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      {/* Suggestions + Input */}
      <div className="border-t border-border">
        <div className="max-w-2xl mx-auto px-4 py-4 space-y-3">
          {/* Suggestions */}
          {!isLoading && suggestions.length > 0 && (
            <Suggestions className="mb-3">
              {suggestions.map((suggestion) => (
                <Suggestion
                  key={suggestion}
                  suggestion={suggestion}
                  onClick={handleSuggestionClick}
                />
              ))}
            </Suggestions>
          )}

          {/* Input */}
          <PromptInput onSubmit={handleSubmit}>
            <PromptInputTextarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about NQ futures..."
            />
            <PromptInputToolbar>
              <PromptInputTools />
              {isLoading ? (
                <button
                  type="button"
                  onClick={stopGeneration}
                  className="inline-flex items-center justify-center rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
                >
                  Stop
                </button>
              ) : (
                <PromptInputSubmit disabled={!input.trim()} />
              )}
            </PromptInputToolbar>
          </PromptInput>
        </div>
      </div>
    </div>
  )
}
