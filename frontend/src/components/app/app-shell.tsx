"use client"

/**
 * AppShell — single point of data access for panels.
 *
 * Connects to data contexts and passes data to panels via props.
 * Panels remain pure presentational components.
 */

import { useState, useCallback, useMemo } from "react"
import { useChatsContext, useAuth } from "@/providers"
import { useChat } from "@/hooks/useChat"
import { PanelsProvider, usePanels } from "@/components/app/panels/panels-provider"
import { SidebarContainer } from "@/components/app/panels/sidebar/sidebar.container"
import { ChatPanelContainer } from "@/components/app/panels/chat-panel/chat-panel.container"
import { ContextPanelContainer } from "@/components/app/panels/context-panel/context-panel.container"
import type { DataCard } from "@/types/chat"

export function AppShell() {
  return (
    <PanelsProvider>
      <AppShellContent />
    </PanelsProvider>
  )
}

function AppShellContent() {
  const { signOut } = useAuth()
  const { setRightOpen } = usePanels()
  const {
    chats,
    currentChatId,
    selectChat,
    createChat,
    deleteChat,
    refreshChats,
    updateChatTitle,
  } = useChatsContext()
  const [inputText, setInputText] = useState("")
  const [contextData, setContextData] = useState<DataCard | null>(null)

  const handleChatCreated = useCallback((chatId: string) => {
    selectChat(chatId)
    refreshChats()
  }, [selectChat, refreshChats])

  const handleOpenContextPanel = useCallback((data: DataCard) => {
    setContextData(data)
    setRightOpen(true)
  }, [setRightOpen])

  const {
    messages,
    isLoading,
    isLoadingHistory,
    currentSteps,
    streamingPreview,
    streamingText,
    streamingDataCard,
    suggestions,
    sendMessage,
    stopGeneration,
    updateFeedback,
  } = useChat({
    chatId: currentChatId,
    onChatCreated: handleChatCreated,
    onTitleUpdated: updateChatTitle,
  })

  const handleSubmit = useCallback(() => {
    if (!inputText.trim()) return
    sendMessage(inputText)
    setInputText("")
  }, [inputText, sendMessage])

  const handleSuggestionClick = useCallback((suggestion: string) => {
    sendMessage(suggestion)
  }, [sendMessage])

  const handleNewChat = useCallback(() => {
    createChat()
  }, [createChat])

  const handleSettings = useCallback(() => {
    // TODO: Navigate to settings
  }, [])

  const currentChat = useMemo(
    () => chats.find((c) => c.id === currentChatId),
    [chats, currentChatId]
  )
  const title = currentChat?.title ?? undefined

  // Map chats to sidebar format (memoized to prevent unnecessary re-renders)
  const sidebarChats = useMemo(() =>
    chats.map((chat) => ({
      id: chat.id,
      title: chat.title || "New Chat",
    }))
  , [chats])

  return (
    <div className="flex h-dvh w-full overflow-hidden">
      <SidebarContainer
        chats={sidebarChats}
        currentChatId={currentChatId}
        onSelectChat={selectChat}
        onNewChat={handleNewChat}
        onSettings={handleSettings}
        onSignOut={signOut}
      />
      <ChatPanelContainer
        title={title}
        messages={messages}
        isLoading={isLoading}
        isLoadingHistory={isLoadingHistory}
        currentSteps={currentSteps}
        streamingPreview={streamingPreview}
        streamingText={streamingText}
        streamingDataCard={streamingDataCard}
        suggestions={suggestions}
        inputText={inputText}
        onInputChange={setInputText}
        onSubmit={handleSubmit}
        onStop={stopGeneration}
        onSuggestionClick={handleSuggestionClick}
        onFeedback={updateFeedback}
        onOpenContextPanel={handleOpenContextPanel}
      />
      <ContextPanelContainer data={contextData} />
    </div>
  )
}
