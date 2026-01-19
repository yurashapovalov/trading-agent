"use client"

import { useState, useEffect, useCallback, useRef } from "react"
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
  const initialChatCreated = useRef(false)

  // Get chatId from URL params (/chat/[id]) or null if on root
  const currentChatId = (params?.id as string) || null

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

        // Auto-redirect to first chat if on root and we have chats
        if (chatList.length > 0) {
          if (!currentChatId && pathname === "/") {
            router.replace(`/chat/${chatList[0].id}`)
          }
        } else if (!initialChatCreated.current) {
          // Create first chat automatically (only once)
          initialChatCreated.current = true
          const title = "New Chat"
          const createResponse = await fetch(`${API_URL}/chats`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${session.access_token}`,
            },
            body: JSON.stringify({ title }),
          })
          if (createResponse.ok) {
            const data = await createResponse.json()
            const newChat: ChatSession = {
              id: data.id,
              title,
              stats: null,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }
            setChats([newChat])
            router.replace(`/chat/${newChat.id}`)
          }
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

  // Create new chat in API
  const createChat = useCallback(async (): Promise<string | null> => {
    if (!session?.access_token) return null

    const title = getNextNewChatTitle(chats)

    try {
      const response = await fetch(`${API_URL}/chats`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ title }),
      })
      if (response.ok) {
        const data = await response.json()
        const newChat: ChatSession = {
          id: data.id,
          title,
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
  }, [session?.access_token, chats, getNextNewChatTitle, router])

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
