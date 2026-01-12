"use client"

import { useState } from "react"
import { useAuth } from "@/components/auth-provider"
import { useChat } from "@/hooks/useChat"

// AI components
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai/conversation"
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai/message"
import {
  ChainOfThought,
  ChainOfThoughtHeader,
  ChainOfThoughtContent,
  ChainOfThoughtStep,
} from "@/components/ai/chain-of-thought"
import { Suggestions, Suggestion } from "@/components/ai/suggestion"
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  type PromptInputMessage,
} from "@/components/ai/prompt-input"
import { Loader } from "@/components/ai/loader"

import type { AgentStep } from "@/types/chat"
import { DatabaseIcon, BrainIcon, CheckCircleIcon, RouteIcon } from "lucide-react"

// Map agent names to icons
const agentIcons: Record<string, any> = {
  // v2 agents
  understander: RouteIcon,
  data_fetcher: DatabaseIcon,
  analyst: BrainIcon,
  validator: CheckCircleIcon,
  // legacy agents
  router: RouteIcon,
  data_agent: DatabaseIcon,
  educator: BrainIcon,
}

function AgentStepsDisplay({ steps, isStreaming }: { steps: AgentStep[]; isStreaming?: boolean }) {
  if (steps.length === 0) return null

  return (
    <ChainOfThought defaultOpen={isStreaming}>
      <ChainOfThoughtHeader>
        {isStreaming ? "Thinking..." : `${steps.length} steps`}
      </ChainOfThoughtHeader>
      <ChainOfThoughtContent>
        {steps.map((step, index) => (
          <ChainOfThoughtStep
            key={index}
            label={step.message}
            status={step.status === "running" ? "active" : "complete"}
            icon={agentIcons[step.agent] || BrainIcon}
            description={step.durationMs ? `${step.durationMs}ms` : undefined}
          />
        ))}
      </ChainOfThoughtContent>
    </ChainOfThought>
  )
}

export default function Chat() {
  const { user, signOut } = useAuth()
  const [text, setText] = useState("")
  const {
    messages,
    isLoading,
    currentSteps,
    streamingText,
    suggestions,
    sendMessage,
    stopGeneration,
  } = useChat()

  const handleSubmit = (message: PromptInputMessage) => {
    if (!message.text?.trim()) return
    sendMessage(message.text)
    setText("")
  }

  const handleSuggestionClick = (suggestion: string) => {
    setText(suggestion)
  }

  return (
    <div className="relative flex h-dvh w-full flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2">
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

      {/* Conversation */}
      <Conversation>
        <ConversationContent className="max-w-2xl mx-auto">
          {messages.map((message, index) => (
            <Message from={message.role} key={index} className="max-w-full">
              <div>
                {/* Agent steps before assistant message */}
                {message.role === "assistant" && message.agent_steps && message.agent_steps.length > 0 && (
                  <AgentStepsDisplay steps={message.agent_steps} />
                )}

                {/* Message content */}
                <MessageContent>
                  <MessageResponse>{message.content}</MessageResponse>
                </MessageContent>

                {/* Usage stats */}
                {message.role === "assistant" && message.usage && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    {message.usage.input_tokens.toLocaleString()} / {message.usage.output_tokens.toLocaleString()}
                    {message.usage.thinking_tokens ? ` / ${message.usage.thinking_tokens.toLocaleString()}` : ""}
                    {" · $"}{message.usage.cost.toFixed(4)}
                  </div>
                )}
              </div>
            </Message>
          ))}

          {/* Streaming state */}
          {currentSteps.length > 0 && (
            <Message from="assistant" className="max-w-full">
              <div>
                <AgentStepsDisplay steps={currentSteps} isStreaming />
              </div>
            </Message>
          )}

          {streamingText && (
            <Message from="assistant" className="max-w-full">
              <MessageContent>
                <MessageResponse>{streamingText}</MessageResponse>
              </MessageContent>
            </Message>
          )}

          {isLoading && currentSteps.length === 0 && !streamingText && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader className="size-4" />
              <span className="text-sm">Thinking...</span>
            </div>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      {/* Bottom: Suggestions + Input */}
      <div className="mx-auto w-full max-w-2xl shrink-0 space-y-4 px-4 pb-4 pt-4">
        {!isLoading && suggestions.length > 0 && (
          <Suggestions>
            {suggestions.map((suggestion) => (
              <Suggestion
                key={suggestion}
                variant="ghost"
                onClick={() => handleSuggestionClick(suggestion)}
                suggestion={suggestion}
              />
            ))}
          </Suggestions>
        )}

        <PromptInput onSubmit={handleSubmit}>
            <PromptInputBody>
              <PromptInputTextarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Ask about NQ futures..."
              />
            </PromptInputBody>
            <PromptInputFooter>
              <PromptInputTools />
              {isLoading ? (
                <button
                  type="button"
                  onClick={stopGeneration}
                  className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
                >
                  Stop
                </button>
              ) : (
                <PromptInputSubmit disabled={!text.trim()} />
              )}
            </PromptInputFooter>
          </PromptInput>
      </div>
    </div>
  )
}
