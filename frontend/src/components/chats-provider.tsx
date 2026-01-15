"use client"

import { createContext, useContext, type ReactNode } from "react"
import { useChats, type ChatSession } from "@/hooks/useChats"

type ChatsContextType = {
  chats: ChatSession[]
  currentChatId: string | null
  isLoading: boolean
  createChat: () => string
  deleteChat: (chatId: string) => Promise<void>
  selectChat: (chatId: string) => void
  updateChatTitle: (chatId: string, title: string) => void
  refreshChats: () => Promise<void>
  materializeChat: (virtualId: string) => Promise<string | null>
  isCurrentChatVirtual: () => boolean
}

const ChatsContext = createContext<ChatsContextType | null>(null)

export function ChatsProvider({ children }: { children: ReactNode }) {
  const chats = useChats()

  return (
    <ChatsContext.Provider value={chats}>
      {children}
    </ChatsContext.Provider>
  )
}

export function useChatsContext() {
  const context = useContext(ChatsContext)
  if (!context) {
    throw new Error("useChatsContext must be used within ChatsProvider")
  }
  return context
}
