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
  isVirtual?: boolean // Not saved to DB yet
}

// Generate temporary ID for virtual chats
const generateVirtualId = () => `virtual_${Date.now()}_${Math.random().toString(36).slice(2)}`

export function useChats() {
  const { session } = useAuth()
  const [chats, setChats] = useState<ChatSession[]>([])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Generate next "New Chat N" title based on current chats
  const getNextNewChatTitle = useCallback((chatList: ChatSession[]) => {
    const existingNewChats = chatList.filter(c =>
      c.title?.startsWith("New Chat")
    )
    if (existingNewChats.length === 0) return "New Chat"

    let maxNum = 1
    for (const chat of existingNewChats) {
      const match = chat.title?.match(/^New Chat\s*(\d*)$/)
      if (match) {
        const num = match[1] ? parseInt(match[1]) : 1
        if (num >= maxNum) maxNum = num + 1
      }
    }
    return `New Chat ${maxNum}`
  }, [])

  // Create virtual chat (local only, no API call)
  const createVirtualChat = useCallback((title: string): ChatSession => {
    return {
      id: generateVirtualId(),
      title,
      stats: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      isVirtual: true,
    }
  }, [])

  // Materialize virtual chat in DB (called on first message)
  const materializeChat = useCallback(async (virtualId: string): Promise<string | null> => {
    if (!session?.access_token) return null

    const virtualChat = chats.find(c => c.id === virtualId)
    if (!virtualChat || !virtualChat.isVirtual) return virtualId // Already real

    try {
      const response = await fetch(`${API_URL}/chats`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ title: virtualChat.title }),
      })
      if (response.ok) {
        const data = await response.json()
        const realId = data.id

        // Replace virtual chat with real one
        setChats((prev) =>
          prev.map((c) =>
            c.id === virtualId
              ? { ...c, id: realId, isVirtual: false }
              : c
          )
        )

        // Update currentChatId if it was the virtual one
        if (currentChatId === virtualId) {
          setCurrentChatId(realId)
        }

        return realId
      }
    } catch (e) {
      console.error("Failed to materialize chat:", e)
    }
    return null
  }, [session?.access_token, chats, currentChatId])

  // Fetch chats from DB
  const fetchChats = useCallback(async () => {
    if (!session?.access_token) return

    try {
      const response = await fetch(`${API_URL}/chats`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (response.ok) {
        const data = await response.json()
        const chatList: ChatSession[] = Array.isArray(data) ? data : []

        if (chatList.length === 0) {
          // No chats in DB - create virtual one locally
          const virtualChat = createVirtualChat("New Chat")
          setChats([virtualChat])
          setCurrentChatId(virtualChat.id)
        } else {
          setChats(chatList)
          // Auto-select first chat if none selected
          if (!currentChatId) {
            setCurrentChatId(chatList[0].id)
          }
        }
      }
    } catch (e) {
      console.error("Failed to fetch chats:", e)
    } finally {
      setIsLoading(false)
    }
  }, [session?.access_token, currentChatId, createVirtualChat])

  useEffect(() => {
    fetchChats()
  }, [fetchChats])

  // Create new chat (virtual, no API call)
  const createChat = useCallback((): string => {
    const title = getNextNewChatTitle(chats)
    const virtualChat = createVirtualChat(title)
    setChats((prev) => [virtualChat, ...prev])
    setCurrentChatId(virtualChat.id)
    return virtualChat.id
  }, [chats, createVirtualChat, getNextNewChatTitle])

  const deleteChat = useCallback(async (chatId: string) => {
    const chatToDelete = chats.find(c => c.id === chatId)

    // If virtual, just remove from state
    if (chatToDelete?.isVirtual) {
      const remainingChats = chats.filter((c) => c.id !== chatId)
      setChats(remainingChats)

      if (currentChatId === chatId) {
        if (remainingChats.length > 0) {
          setCurrentChatId(remainingChats[0].id)
        } else {
          // Create new virtual chat
          const virtualChat = createVirtualChat("New Chat")
          setChats([virtualChat])
          setCurrentChatId(virtualChat.id)
        }
      }
      return
    }

    // Real chat - delete from DB
    if (!session?.access_token) return

    try {
      const response = await fetch(`${API_URL}/chats/${chatId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (response.ok) {
        const remainingChats = chats.filter((c) => c.id !== chatId)
        setChats(remainingChats)

        if (currentChatId === chatId) {
          if (remainingChats.length > 0) {
            setCurrentChatId(remainingChats[0].id)
          } else {
            // All chats deleted - create virtual one
            const virtualChat = createVirtualChat("New Chat")
            setChats([virtualChat])
            setCurrentChatId(virtualChat.id)
          }
        }
      }
    } catch (e) {
      console.error("Failed to delete chat:", e)
    }
  }, [session?.access_token, currentChatId, chats, createVirtualChat])

  const selectChat = useCallback((chatId: string) => {
    setCurrentChatId(chatId)
  }, [])

  const updateChatTitle = useCallback((chatId: string, title: string) => {
    setChats((prev) =>
      prev.map((c) => (c.id === chatId ? { ...c, title } : c))
    )
  }, [])

  // Check if current chat is virtual
  const isCurrentChatVirtual = useCallback(() => {
    const current = chats.find(c => c.id === currentChatId)
    return current?.isVirtual ?? false
  }, [chats, currentChatId])

  return {
    chats,
    currentChatId,
    isLoading,
    createChat,
    deleteChat,
    selectChat,
    updateChatTitle,
    refreshChats: fetchChats,
    materializeChat,
    isCurrentChatVirtual,
  }
}
