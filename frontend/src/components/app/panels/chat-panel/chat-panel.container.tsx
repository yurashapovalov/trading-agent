"use client"

/**
 * ChatPanelContainer — logic layer for ChatPanel.
 *
 * Handles:
 * - Visibility based on panel state (showMainContent)
 * - Connects UI state from PanelsProvider to ChatPanel props
 *
 * Data comes from AppShell via props.
 */

import { usePanels } from "../panels-provider"
import { ChatPanel } from "./chat-panel"
import type { ChatMessage, AgentStep, DataCard } from "@/types/chat"

type ChatPanelContainerProps = {
  title?: string
  messages: ChatMessage[]
  isLoading: boolean
  isLoadingHistory: boolean
  currentSteps: AgentStep[]
  streamingPreview: string
  streamingText: string
  streamingDataCard: DataCard | null
  suggestions: string[]
  inputText: string
  onInputChange: (text: string) => void
  onSubmit: () => void
  onStop: () => void
  onSuggestionClick: (suggestion: string) => void
  onFeedback: (requestId: string, type: "positive" | "negative", text: string) => void
  onOpenContextPanel: (data: DataCard) => void
}

export function ChatPanelContainer(props: ChatPanelContainerProps) {
  const { showMainContent, leftOpen, setLeftOpen } = usePanels()

  if (!showMainContent) return null

  return (
    <ChatPanel
      {...props}
      sidebarOpen={leftOpen}
      onOpenSidebar={() => setLeftOpen(true)}
    />
  )
}
