"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
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
        // No auto-redirect: / = new chat screen
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

  // Start new chat - creates session immediately and navigates to it
  const createChat = useCallback(async () => {
    if (!session?.access_token) {
      router.push("/")
      return
    }

    try {
      const response = await fetch(`${API_URL}/chats`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({}),
      })

      if (response.ok) {
        const newChat: ChatSession = await response.json()
        // Add to local state immediately
        setChats((prev) => [newChat, ...prev])
        // Navigate to new chat
        router.push(`/chat/${newChat.id}`)
      } else {
        // Fallback to old behavior
        router.push("/")
      }
    } catch (e) {
      console.error("Failed to create chat:", e)
      router.push("/")
    }
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
