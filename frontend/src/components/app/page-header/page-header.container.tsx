"use client"

import { PanelLeftIcon, PanelRightIcon } from "lucide-react"
import { useSidebar } from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { PageHeader } from "./page-header"

type PageHeaderContainerProps = {
  title: string
  userEmail?: string
}

export function PageHeaderContainer({ title, userEmail }: PageHeaderContainerProps) {
  const leftSidebar = useSidebar("left")
  const rightSidebar = useSidebar("right")

  const isLeftOpen = leftSidebar.isMobile ? leftSidebar.openMobile : leftSidebar.open
  const isRightOpen = rightSidebar.isMobile ? rightSidebar.openMobile : rightSidebar.open

  const handleOpenLeft = () => {
    if (leftSidebar.isMobile) {
      leftSidebar.setOpenMobile(true)
    } else {
      leftSidebar.setOpen(true)
    }
  }

  const handleOpenRight = () => {
    if (rightSidebar.isMobile) {
      rightSidebar.setOpenMobile(true)
    } else {
      rightSidebar.setOpen(true)
    }
  }

  return (
    <PageHeader
      title={title}
      subtitle={userEmail}
      leftAction={
        !isLeftOpen ? (
          <Button
            variant="ghost"
            size="icon"
            className="-ml-1 size-7"
            onClick={handleOpenLeft}
          >
            <PanelLeftIcon className="size-4" />
            <span className="sr-only">Open left panel</span>
          </Button>
        ) : undefined
      }
      rightAction={
        !isRightOpen ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={handleOpenRight}
          >
            <PanelRightIcon className="size-4" />
            <span className="sr-only">Open right panel</span>
          </Button>
        ) : undefined
      }
    />
  )
}
