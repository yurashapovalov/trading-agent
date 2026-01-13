"use client"

import { PanelRightIcon } from "lucide-react"
import { useSidebar, SidebarTrigger } from "@/components/ui/sidebar"
import { RightPanel } from "./right-panel"

export function RightPanelContainer() {
  const { isMobile, setOpen, setOpenMobile } = useSidebar("right")

  const handleClose = () => {
    if (isMobile) {
      setOpenMobile(false)
    } else {
      setOpen(false)
    }
  }
  const handleSelectPinned = (id: string) => {
    // TODO: Implement pinned selection
    console.log("Select pinned:", id)
  }
  const handleSelectArtifact = (id: string) => {
    // TODO: Implement artifact selection
    console.log("Select artifact:", id)
  }

  return (
    <RightPanel
      pinnedItems={[]}
      artifacts={[]}
      onClose={handleClose}
      onSelectPinned={handleSelectPinned}
      onSelectArtifact={handleSelectArtifact}
    />
  )
}

export function RightPanelTrigger({ className }: { className?: string }) {
  return (
    <SidebarTrigger side="right" className={className}>
      <PanelRightIcon className="size-4" />
      <span className="sr-only">Toggle right panel</span>
    </SidebarTrigger>
  )
}
