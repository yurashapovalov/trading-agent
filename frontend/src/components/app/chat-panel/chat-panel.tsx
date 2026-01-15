"use client"

import { useState } from "react"
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
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai/prompt-input"
import { Loader } from "@/components/ai/loader"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

import type { AgentStep, ChatMessage } from "@/types/chat"
import { DatabaseIcon, BrainIcon, CheckCircleIcon, RouteIcon, MessageCircleIcon, CodeIcon, ThumbsUpIcon, ThumbsDownIcon } from "lucide-react"
import { Actions, Action } from "@/components/ai/actions"

// Map agent names to icons
const agentIcons: Record<string, any> = {
  understander: RouteIcon,
  query_builder: CodeIcon,
  responder: MessageCircleIcon,
  data_fetcher: DatabaseIcon,
  analyst: BrainIcon,
  validator: CheckCircleIcon,
}

function getStepDescription(step: AgentStep): string | undefined {
  const parts: string[] = []

  if (step.durationMs) {
    parts.push(`${step.durationMs}ms`)
  }

  if (step.result) {
    if (step.agent === "understander") {
      const type = step.result.type as string
      const symbol = step.result.symbol as string
      if (type) parts.push(`→ ${type}`)
      if (symbol) parts.push(symbol)
    } else if (step.agent === "query_builder") {
      const sqlGenerated = step.result.sql_generated as boolean
      if (sqlGenerated) parts.push("SQL ✓")
    } else if (step.agent === "data_fetcher") {
      const rows = step.result.rows as number
      if (rows !== undefined) parts.push(`${rows} rows`)
    } else if (step.agent === "analyst") {
      const len = step.result.response_length as number
      if (len) parts.push(`${len} chars`)
    } else if (step.agent === "validator") {
      const status = step.result.status as string
      if (status) parts.push(status === "ok" ? "✓" : "rewrite")
    } else if (step.agent === "responder") {
      const len = step.result.response_length as number
      if (len) parts.push(`${len} chars`)
    }
  }

  return parts.length > 0 ? parts.join(" · ") : undefined
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
            description={getStepDescription(step)}
          />
        ))}
      </ChainOfThoughtContent>
    </ChainOfThought>
  )
}

type ChatPanelProps = {
  header?: React.ReactNode
  messages: ChatMessage[]
  isLoading: boolean
  currentSteps: AgentStep[]
  streamingText: string
  suggestions: string[]
  inputText: string
  onInputChange: (text: string) => void
  onSubmit: () => void
  onStop: () => void
  onSuggestionClick: (suggestion: string) => void
  onFeedback: (requestId: string, type: "positive" | "negative", text: string) => void
}

type FeedbackModal = {
  open: boolean
  requestId: string
  type: "positive" | "negative"
  existingText: string
}

export function ChatPanel({
  header,
  messages,
  isLoading,
  currentSteps,
  streamingText,
  suggestions,
  inputText,
  onInputChange,
  onSubmit,
  onStop,
  onSuggestionClick,
  onFeedback,
}: ChatPanelProps) {
  const [feedbackModal, setFeedbackModal] = useState<FeedbackModal>({
    open: false,
    requestId: "",
    type: "positive",
    existingText: "",
  })
  const [feedbackText, setFeedbackText] = useState("")

  const openFeedbackModal = (requestId: string, type: "positive" | "negative", existingText: string = "") => {
    setFeedbackModal({ open: true, requestId, type, existingText })
    setFeedbackText(existingText)
  }

  const closeFeedbackModal = () => {
    setFeedbackModal({ ...feedbackModal, open: false })
    setFeedbackText("")
  }

  const submitFeedback = () => {
    if (feedbackText.trim()) {
      onFeedback(feedbackModal.requestId, feedbackModal.type, feedbackText.trim())
    }
    closeFeedbackModal()
  }

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden">
      {header}

      {/* Conversation */}
      <Conversation>
        <ConversationContent className="max-w-2xl mx-auto">
          {messages.map((message, index) => (
            <Message from={message.role} key={index} className="max-w-full group">
              <div>
                {message.role === "assistant" && message.agent_steps && message.agent_steps.length > 0 && (
                  <AgentStepsDisplay steps={message.agent_steps} />
                )}

                <MessageContent>
                  <MessageResponse>{message.content}</MessageResponse>
                </MessageContent>

                {message.role === "assistant" && message.request_id && (
                  <div className={`mt-2 transition-opacity duration-200 ${
                    message.feedback?.positive_feedback || message.feedback?.negative_feedback
                      ? "opacity-100"
                      : "opacity-0 group-hover:opacity-100"
                  }`}>
                    <Actions>
                      <Action
                        tooltip="Give positive feedback"
                        onClick={() => openFeedbackModal(
                          message.request_id!,
                          "positive",
                          message.feedback?.positive_feedback || ""
                        )}
                        className={message.feedback?.positive_feedback ? "text-foreground" : ""}
                      >
                        <ThumbsUpIcon className="size-4" />
                      </Action>
                      <Action
                        tooltip="Give negative feedback"
                        onClick={() => openFeedbackModal(
                          message.request_id!,
                          "negative",
                          message.feedback?.negative_feedback || ""
                        )}
                        className={message.feedback?.negative_feedback ? "text-foreground" : ""}
                      >
                        <ThumbsDownIcon className="size-4" />
                      </Action>
                    </Actions>
                  </div>
                )}
              </div>
            </Message>
          ))}

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
      <div className="mx-auto w-full max-w-2xl shrink-0 px-4 pb-4 pt-4">
        {/* Quick reply suggestions */}
        {suggestions.length > 0 && !isLoading && (
          <div className="mb-3 flex flex-wrap gap-2">
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                type="button"
                onClick={() => onSuggestionClick(suggestion)}
                className="rounded-full border border-border bg-background px-3 py-1.5 text-sm text-foreground hover:bg-muted transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <PromptInput onSubmit={onSubmit}>
          <PromptInputBody>
            <PromptInputTextarea
              value={inputText}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder="Ask about NQ futures..."
            />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputTools />
            {isLoading ? (
              <button
                type="button"
                onClick={onStop}
                className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
              >
                Stop
              </button>
            ) : (
              <PromptInputSubmit disabled={!inputText.trim()} />
            )}
          </PromptInputFooter>
        </PromptInput>
      </div>

      {/* Feedback Modal */}
      <Dialog open={feedbackModal.open} onOpenChange={(open) => !open && closeFeedbackModal()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {feedbackModal.type === "positive" ? "What did you like?" : "What could be improved?"}
            </DialogTitle>
          </DialogHeader>
          <Textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder={feedbackModal.type === "positive"
              ? "Tell us what was helpful..."
              : "Tell us what went wrong..."
            }
            rows={4}
          />
          <DialogFooter>
            <Button variant="outline" onClick={closeFeedbackModal}>
              Cancel
            </Button>
            <Button onClick={submitFeedback} disabled={!feedbackText.trim()}>
              Submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
