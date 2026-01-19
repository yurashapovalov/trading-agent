"use client"

/**
 * ContextPanelContainer — logic layer for ContextPanel.
 *
 * Handles:
 * - Resize behavior (usePanels + usePercentResize)
 * - Open/close state
 * - Mobile: change body background when open
 *
 * Data comes from AppShell via props.
 */

import { useEffect } from "react"
import { usePanels, COOKIE_RIGHT_PERCENT } from "../panels-provider"
import { usePercentResize } from "@/hooks/use-percent-resize"
import { ContextPanel } from "./context-panel"
import type { DataCard } from "@/types/chat"

type ContextPanelContainerProps = {
  data: DataCard | null
}

export function ContextPanelContainer({ data }: ContextPanelContainerProps) {
  const {
    rightOpen,
    setRightOpen,
    rightWidthPercent,
    setRightWidthPercent,
    rightMinPercent,
    rightMaxPercent,
    isMobile,
  } = usePanels()

  const { handleMouseDown } = usePercentResize({
    direction: "right",
    currentPercent: rightWidthPercent,
    minPercent: rightMinPercent,
    maxPercent: rightMaxPercent,
    onResize: setRightWidthPercent,
    cookieName: COOKIE_RIGHT_PERCENT,
  })

  // Mobile: change body background when context panel is open
  useEffect(() => {
    if (rightOpen && isMobile) {
      document.body.style.backgroundColor = "var(--bg-primary)"
      return () => {
        document.body.style.backgroundColor = ""
      }
    }
  }, [rightOpen, isMobile])

  if (!rightOpen) return null

  return (
    <ContextPanel
      widthPercent={isMobile ? 100 : rightWidthPercent}
      onResizeMouseDown={isMobile ? undefined : handleMouseDown}
      onClose={() => setRightOpen(false)}
      isMobile={isMobile}
      data={data}
    />
  )
}
