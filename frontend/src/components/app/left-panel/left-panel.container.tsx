"use client"

import { useAuth } from "@/components/auth-provider"
import { useSidebar } from "@/components/ui/sidebar"
import { LeftPanel } from "./left-panel"

// TODO: Replace with real data from API/state
const mockHistory = [
  { id: "1", title: "NQ Statistics" },
  { id: "2", title: "Entry Points Analysis" },
  { id: "3", title: "Backtest 9:30" },
]

export function LeftPanelContainer() {
  const { signOut } = useAuth()
  const { isMobile, setOpen, setOpenMobile } = useSidebar("left")

  const handleClose = () => {
    if (isMobile) {
      setOpenMobile(false)
    } else {
      setOpen(false)
    }
  }
  const handleNewChat = () => {
    // TODO: Implement new chat
    console.log("New chat")
  }
  const handleSelectChat = (id: string) => {
    // TODO: Implement chat selection
    console.log("Select chat:", id)
  }
  const handleSettings = () => {
    // TODO: Implement settings
    console.log("Settings")
  }

  return (
    <LeftPanel
      history={mockHistory}
      onClose={handleClose}
      onNewChat={handleNewChat}
      onSelectChat={handleSelectChat}
      onSettings={handleSettings}
      onSignOut={signOut}
    />
  )
}
