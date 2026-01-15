"use client"

import { useAuth } from "@/components/auth-provider"
import { useChatsContext } from "@/components/chats-provider"
import { useSidebar } from "@/components/ui/sidebar"
import { LeftPanel } from "./left-panel"

export function LeftPanelContainer() {
  const { signOut } = useAuth()
  const { chats, currentChatId, createChat, selectChat, deleteChat } = useChatsContext()
  const { isMobile, setOpen, setOpenMobile } = useSidebar("left")

  const handleClose = () => {
    if (isMobile) {
      setOpenMobile(false)
    } else {
      setOpen(false)
    }
  }

  const handleNewChat = async () => {
    await createChat()
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  const handleSelectChat = (id: string) => {
    selectChat(id)
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  const handleDeleteChat = async (id: string) => {
    await deleteChat(id)
  }

  const handleSettings = () => {
    // TODO: Navigate to settings page
    console.log("Settings")
  }

  const history = (chats || []).map((chat) => ({
    id: chat.id,
    title: chat.title || "New Chat",
  }))

  return (
    <LeftPanel
      history={history}
      currentChatId={currentChatId}
      onClose={handleClose}
      onNewChat={handleNewChat}
      onSelectChat={handleSelectChat}
      onDeleteChat={handleDeleteChat}
      onSettings={handleSettings}
      onSignOut={signOut}
    />
  )
}
