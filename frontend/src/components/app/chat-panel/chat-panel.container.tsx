"use client"

import { useState, useCallback } from "react"
import { useAuth } from "@/components/auth-provider"
import { useChatsContext } from "@/components/chats-provider"
import { useChat } from "@/hooks/useChat"
import { ChatPanel } from "./chat-panel"
import { PageHeaderContainer } from "@/components/app/page-header/page-header.container"

export default function ChatPanelContainer() {
  const { user } = useAuth()
  const { currentChatId, selectChat, refreshChats, updateChatTitle } = useChatsContext()
  const [text, setText] = useState("")

  const handleChatCreated = useCallback((chatId: string) => {
    selectChat(chatId)
    refreshChats()
  }, [selectChat, refreshChats])

  const {
    messages,
    isLoading,
    currentSteps,
    streamingText,
    suggestions,
    sendMessage,
    stopGeneration,
  } = useChat({
    chatId: currentChatId,
    onChatCreated: handleChatCreated,
    onTitleUpdated: updateChatTitle,
  })

  const handleSubmit = async () => {
    if (!text.trim()) return
    sendMessage(text)
    setText("")
  }

  const handleSuggestionClick = async (suggestion: string) => {
    sendMessage(suggestion)
  }

  return (
    <ChatPanel
      header={
        <PageHeaderContainer
          title="Trading Analytics"
          userEmail={user?.email}
        />
      }
      messages={messages}
      isLoading={isLoading}
      currentSteps={currentSteps}
      streamingText={streamingText}
      suggestions={suggestions}
      inputText={text}
      onInputChange={setText}
      onSubmit={handleSubmit}
      onStop={stopGeneration}
      onSuggestionClick={handleSuggestionClick}
    />
  )
}
