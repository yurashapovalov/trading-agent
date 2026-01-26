"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter, usePathname } from "next/navigation"
import { useAuth } from "@/providers"

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
  const router = useRouter()
  const params = useParams()
  const pathname = usePathname()
  const [chats, setChats] = useState<ChatSession[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Get chatId from URL params (/chat/[id]) or null if on root
  const currentChatId = (params?.id as string) || null

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
        setChats(chatList)

        // Auto-redirect to last chat if on root and we have chats
        // (no auto-create - new chat created on first message or via button)
        if (chatList.length > 0 && !currentChatId && pathname === "/") {
          router.replace(`/chat/${chatList[0].id}`)
        }
      }
    } catch (e) {
      console.error("Failed to fetch chats:", e)
    } finally {
      setIsLoading(false)
    }
  }, [session?.access_token, currentChatId, pathname, router])

  useEffect(() => {
    fetchChats()
  }, [fetchChats])

  // Create new chat in API (used by "New Chat" button)
  const createChat = useCallback(async (): Promise<string | null> => {
    if (!session?.access_token) return null

    try {
      const response = await fetch(`${API_URL}/chats`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ title: "New Chat" }),
      })
      if (response.ok) {
        const data = await response.json()
        const newChat: ChatSession = {
          id: data.id,
          title: "New Chat",
          stats: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
        setChats((prev) => [newChat, ...prev])
        router.push(`/chat/${newChat.id}`)
        return newChat.id
      }
    } catch (e) {
      console.error("Failed to create chat:", e)
    }
    return null
  }, [session?.access_token, router])

  const deleteChat = useCallback(async (chatId: string) => {
    if (!session?.access_token) return

    try {
      const response = await fetch(`${API_URL}/chats/${chatId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (response.ok) {
        const remainingChats = chats.filter((c) => c.id !== chatId)
        setChats(remainingChats)

        // Navigate to another chat if we deleted the current one
        if (currentChatId === chatId) {
          if (remainingChats.length > 0) {
            router.replace(`/chat/${remainingChats[0].id}`)
          } else {
            router.replace("/")
          }
        }
      }
    } catch (e) {
      console.error("Failed to delete chat:", e)
    }
  }, [session?.access_token, currentChatId, chats, router])

  const selectChat = useCallback((chatId: string) => {
    router.push(`/chat/${chatId}`)
  }, [router])

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
