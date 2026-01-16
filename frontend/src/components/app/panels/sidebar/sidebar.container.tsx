"use client"

/**
 * SidebarContainer — logic layer for Sidebar.
 *
 * Handles:
 * - Resize behavior (usePanels + usePixelResize)
 * - Open/close state
 *
 * Data comes from AppShell via props.
 */

import { usePanels, COOKIE_LEFT_WIDTH } from "../panels-provider"
import { usePixelResize } from "@/hooks/use-pixel-resize"
import { Sidebar } from "./sidebar"
import type { ChatItem } from "@/types/chat"

type SidebarContainerProps = {
  // Data from AppShell
  chats: ChatItem[]
  currentChatId: string | null
  // Actions from AppShell
  onSelectChat: (id: string) => void
  onNewChat: () => void
  onDeleteChat: (id: string) => void
  onSettings: () => void
  onSignOut: () => void
}

export function SidebarContainer({
  chats,
  currentChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  onSettings,
  onSignOut,
}: SidebarContainerProps) {
  const { leftOpen, setLeftOpen, leftWidth, setLeftWidth, leftMinWidth, leftMaxWidth, isMobile, showMainContent } = usePanels()

  const { handleMouseDown } = usePixelResize({
    direction: "left",
    currentWidth: leftWidth,
    minWidth: leftMinWidth,
    maxWidth: leftMaxWidth,
    onResize: setLeftWidth,
    cookieName: COOKIE_LEFT_WIDTH,
  })

  if (!leftOpen || !showMainContent) return null

  // Mobile: 80vw width, no resize
  const mobileWidth = typeof window !== "undefined" ? window.innerWidth * 0.8 : 300

  // Mobile: close sidebar after selecting chat
  const handleSelectChat = (id: string) => {
    onSelectChat(id)
    if (isMobile) {
      setLeftOpen(false)
    }
  }

  return (
    <Sidebar
      width={isMobile ? mobileWidth : leftWidth}
      onResizeMouseDown={isMobile ? undefined : handleMouseDown}
      chats={chats}
      currentChatId={currentChatId}
      onSelectChat={handleSelectChat}
      onNewChat={onNewChat}
      onDeleteChat={onDeleteChat}
      onClose={() => setLeftOpen(false)}
      onSettings={onSettings}
      onSignOut={onSignOut}
    />
  )
}
