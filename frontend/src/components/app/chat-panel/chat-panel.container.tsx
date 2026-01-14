"use client"

import { useState } from "react"
import { useAuth } from "@/components/auth-provider"
import { useChat } from "@/hooks/useChat"
import { ChatPanel } from "./chat-panel"
import { PageHeaderContainer } from "@/components/app/page-header/page-header.container"

export default function ChatPanelContainer() {
  const { user } = useAuth()
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

  const handleSubmit = () => {
    if (!text.trim()) return
    sendMessage(text)
    setText("")
  }

  const handleSuggestionClick = (suggestion: string) => {
    // Send suggestion as a normal message
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
