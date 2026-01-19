"use client"

/**
 * ChatPanel — presentational component.
 *
 * Receives all data and UI callbacks via props.
 * No logic, no context access — just renders what it's given.
 */

import { useState, useRef, useEffect } from "react"
import { PanelLeft, PanelRight, ThumbsUpIcon, ThumbsDownIcon } from "lucide-react"
import {
  PageHeader,
  PageHeaderLeft,
  PageHeaderRight,
} from "@/components/app/page-header/page-header"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
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
  PromptInput,
  PromptInputBody,
  PromptInputTextarea,
  PromptInputFooter,
  PromptInputTools,
  PromptInputSubmit,
} from "@/components/ai/prompt-input"
import { Suggestions, Suggestion } from "@/components/ai/suggestion"
import { Actions, Action } from "@/components/ai/actions"
import { Processed } from "@/components/app/processed/processed"
import { DataCard } from "@/components/ai/data-card"
import { Skeleton } from "@/components/ui/skeleton"
import type { ChatMessage, AgentStep, DataCard as DataCardType } from "@/types/chat"

type FeedbackModal = {
  open: boolean
  requestId: string
  type: "positive" | "negative"
}

type ChatPanelProps = {
  // Data
  title?: string
  messages: ChatMessage[]
  isLoading: boolean
  isLoadingHistory: boolean
  currentSteps: AgentStep[]
  streamingPreview: string
  streamingText: string
  streamingDataCard: DataCardType | null
  suggestions: string[]
  inputText: string
  // Data callbacks
  onInputChange: (text: string) => void
  onSubmit: () => void
  onStop: () => void
  onSuggestionClick: (suggestion: string) => void
  onFeedback: (requestId: string, type: "positive" | "negative", text: string) => void
  // UI state
  sidebarOpen: boolean
  contextPanelOpen: boolean
  // UI callbacks
  onOpenSidebar: () => void
  onOpenContextPanel: () => void
}

export function ChatPanel({
  title,
  messages,
  isLoading,
  isLoadingHistory,
  currentSteps,
  streamingPreview,
  streamingText,
  streamingDataCard,
  suggestions,
  inputText,
  onInputChange,
  onSubmit,
  onStop,
  onSuggestionClick,
  onFeedback,
  sidebarOpen,
  contextPanelOpen,
  onOpenSidebar,
  onOpenContextPanel,
}: ChatPanelProps) {
  const [feedbackModal, setFeedbackModal] = useState<FeedbackModal>({
    open: false,
    requestId: "",
    type: "positive",
  })
  const [feedbackText, setFeedbackText] = useState("")
  const inputContainerRef = useRef<HTMLDivElement>(null)
  const [inputContainerHeight, setInputContainerHeight] = useState(0)

  // Measure input container height for scroll button positioning
  useEffect(() => {
    const container = inputContainerRef.current
    if (!container) return

    const observer = new ResizeObserver(() => {
      // offsetHeight includes padding
      setInputContainerHeight(container.offsetHeight)
    })

    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  const openFeedbackModal = (requestId: string, type: "positive" | "negative", existingText: string = "") => {
    setFeedbackModal({ open: true, requestId, type })
    setFeedbackText(existingText)
  }

  const closeFeedbackModal = () => {
    setFeedbackModal({ open: false, requestId: "", type: "positive" })
    setFeedbackText("")
  }

  const submitFeedback = () => {
    if (feedbackText.trim()) {
      onFeedback(feedbackModal.requestId, feedbackModal.type, feedbackText.trim())
    }
    closeFeedbackModal()
  }

  return (
    <div className="relative flex h-full w-full shrink-0 flex-col overflow-hidden bg-[var(--bg-secondary)] md:w-auto md:shrink md:flex-1">
      <PageHeader>
        <PageHeaderLeft>
          {!sidebarOpen && (
            <Button variant="ghost" size="icon-sm" onClick={onOpenSidebar} aria-label="Open sidebar">
              <PanelLeft />
            </Button>
          )}
          <span className="text-sm font-medium">{title ?? "New Chat"}</span>
        </PageHeaderLeft>
        <PageHeaderRight>
          {!contextPanelOpen && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onOpenContextPanel}
              aria-label="Open context panel"
            >
              <PanelRight />
            </Button>
          )}
        </PageHeaderRight>
      </PageHeader>

      {/* Messages area with padding for input */}
      <Conversation>
        <ConversationContent
          className="mx-auto max-w-2xl"
          style={{ paddingBottom: (inputContainerHeight || 128) + 48 }}
        >
          {/* Loading skeletons */}
          {isLoadingHistory && messages.length === 0 && (
            <div className="space-y-6">
              {/* User message skeleton */}
              <div className="flex justify-end">
                <Skeleton className="h-10 w-48 rounded-lg" />
              </div>
              {/* Assistant message skeleton */}
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-5/6" />
              </div>
              {/* Another pair */}
              <div className="flex justify-end">
                <Skeleton className="h-10 w-32 rounded-lg" />
              </div>
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            </div>
          )}

          {(() => {
            const lastAssistantIndex = messages.findLastIndex(m => m.role === "assistant")
            return messages.map((message, index) => {
              const isLastAssistant = message.role === "assistant" && index === lastAssistantIndex

              return (
                <Message
                  from={message.role}
                  key={message.request_id ?? `${message.role}-${index}`}
                  className="group"
                >
                <div>
                  {message.role === "assistant" && message.agent_steps && message.agent_steps.length > 0 && (
                    <div className="mb-2">
                      <Processed steps={message.agent_steps} isLoading={false} />
                    </div>
                  )}

                  {/* Preview text (expert context before data) */}
                  {message.role === "assistant" && message.preview && (
                    <MessageContent className="mb-2">
                      <MessageResponse>{message.preview}</MessageResponse>
                    </MessageContent>
                  )}

                  {/* Data card (between preview and summary) */}
                  {message.role === "assistant" && message.data_card && (
                    <DataCard data={message.data_card} onClick={onOpenContextPanel} />
                  )}

                  {/* Main content (summary or full response) */}
                  <MessageContent>
                    <MessageResponse>{message.content}</MessageResponse>
                  </MessageContent>

                  {message.role === "assistant" && message.request_id && (
                    <div className={`mt-2 transition-opacity duration-200 ${
                      isLastAssistant
                        ? "opacity-100"
                        : "opacity-0 group-hover:opacity-100"
                    }`}>
                      <Actions>
                        <Action
                          tooltip="Positive feedback"
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
                          tooltip="Negative feedback"
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
              )
            })
          })()}

          {currentSteps.length > 0 && (
            <Message from="assistant" className="">
              <div>
                <Processed steps={currentSteps} isLoading={true} />
              </div>
            </Message>
          )}

          {/* Streaming content - shows preview, data card, and summary separately */}
          {(streamingPreview || streamingDataCard || streamingText) && (
            <Message from="assistant" className="">
              <div>
                {/* Preview text (before data) */}
                {streamingPreview && (
                  <MessageContent className="mb-2">
                    <MessageResponse>{streamingPreview}</MessageResponse>
                  </MessageContent>
                )}

                {/* Data card (when data arrives) */}
                {streamingDataCard && (
                  <DataCard data={streamingDataCard} onClick={onOpenContextPanel} />
                )}

                {/* Summary text (after data) */}
                {streamingText && (
                  <MessageContent>
                    <MessageResponse>{streamingText}</MessageResponse>
                  </MessageContent>
                )}
              </div>
            </Message>
          )}

          {isLoading && currentSteps.length === 0 && !streamingPreview && !streamingText && (
            <Message from="assistant" className="">
              <div>
                <Processed steps={[]} isLoading={true} />
              </div>
            </Message>
          )}
        </ConversationContent>
        <ConversationScrollButton style={{ bottom: inputContainerHeight || 144 }} />
      </Conversation>

      {/* Input area - absolute positioned at bottom */}
      <div
        ref={inputContainerRef}
        className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[var(--bg-secondary)] via-[var(--bg-secondary)] to-transparent pt-2 pb-8 md:pb-4 px-4"
      >
        <div className="mx-auto max-w-2xl">
          {/* Suggestions */}
          {suggestions.length > 0 && !isLoading && (
            <Suggestions className="mb-3">
              {suggestions.map((suggestion) => (
                <Suggestion
                  key={suggestion}
                  suggestion={suggestion}
                  onClick={onSuggestionClick}
                />
              ))}
            </Suggestions>
          )}

          {/* Input */}
          <PromptInput onSubmit={onSubmit}>
            <PromptInputBody>
              <PromptInputTextarea
                value={inputText}
                onChange={(e) => onInputChange(e.target.value)}
                placeholder="Ask something..."
              />
            </PromptInputBody>
            <PromptInputFooter>
              <PromptInputTools />
              {isLoading ? (
                <Button variant="destructive" size="sm" onClick={onStop}>
                  Stop
                </Button>
              ) : (
                <PromptInputSubmit disabled={!inputText.trim()} />
              )}
            </PromptInputFooter>
          </PromptInput>
        </div>
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
            className="min-h-48 field-sizing-fixed"
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
