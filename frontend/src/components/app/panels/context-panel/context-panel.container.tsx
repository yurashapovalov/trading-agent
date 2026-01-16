"use client"

/**
 * ContextPanelContainer — logic layer for ContextPanel.
 *
 * Handles:
 * - Resize behavior (usePanels + usePercentResize)
 * - Open/close state
 *
 * Data comes from AppShell via props.
 */

import { usePanels, COOKIE_RIGHT_PERCENT } from "../panels-provider"
import { usePercentResize } from "@/hooks/use-percent-resize"
import { ContextPanel } from "./context-panel"

export function ContextPanelContainer() {
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

  if (!rightOpen) return null

  return (
    <ContextPanel
      widthPercent={isMobile ? 100 : rightWidthPercent}
      onResizeMouseDown={isMobile ? undefined : handleMouseDown}
      onClose={() => setRightOpen(false)}
      isMobile={isMobile}
    />
  )
}
