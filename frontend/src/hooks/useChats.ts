"use client"

import { useState, useEffect, useCallback } from "react"
import { useAuth } from "@/components/auth-provider"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export type ChatSession = {
  id: string
  title: string | null
  stats: {
    message_count: number
    input_tokens: number
    output_tokens: number
    thinking_tokens: number
    cost_usd: number
  } | null
  created_at: string
  updated_at: string
}

export function useChats() {
  const { session } = useAuth()
  const [chats, setChats] = useState<ChatSession[]>([])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchChats = useCallback(async () => {
    if (!session?.access_token) return

    try {
      const response = await fetch(`${API_URL}/chats`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (response.ok) {
        const data = await response.json()
        setChats(data.chats)
      }
    } catch (e) {
      console.error("Failed to fetch chats:", e)
    } finally {
      setIsLoading(false)
    }
  }, [session?.access_token])

  useEffect(() => {
    fetchChats()
  }, [fetchChats])

  const createChat = useCallback(async (): Promise<string | null> => {
    if (!session?.access_token) return null

    try {
      const response = await fetch(`${API_URL}/chats`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
      })
      if (response.ok) {
        const data = await response.json()
        const newChat: ChatSession = {
          id: data.id,
          title: null,
          stats: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
        setChats((prev) => [newChat, ...prev])
        setCurrentChatId(data.id)
        return data.id
      }
    } catch (e) {
      console.error("Failed to create chat:", e)
    }
    return null
  }, [session?.access_token])

  const deleteChat = useCallback(async (chatId: string) => {
    if (!session?.access_token) return

    try {
      const response = await fetch(`${API_URL}/chats/${chatId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (response.ok) {
        setChats((prev) => prev.filter((c) => c.id !== chatId))
        // Switch to another chat if deleting current
        if (currentChatId === chatId) {
          setCurrentChatId(null)
        }
      }
    } catch (e) {
      console.error("Failed to delete chat:", e)
    }
  }, [session?.access_token, currentChatId])

  const selectChat = useCallback((chatId: string) => {
    setCurrentChatId(chatId)
  }, [])

  const updateChatTitle = useCallback((chatId: string, title: string) => {
    setChats((prev) =>
      prev.map((c) => (c.id === chatId ? { ...c, title } : c))
    )
  }, [])

  return {
    chats,
    currentChatId,
    isLoading,
    createChat,
    deleteChat,
    selectChat,
    updateChatTitle,
    refreshChats: fetchChats,
  }
}
