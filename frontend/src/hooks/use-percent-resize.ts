"use client"

/**
 * Hook for percentage-based panel resize.
 *
 * Converts mouse drag to percentage change relative to viewport width.
 * Saves to cookie on drag end.
 */

import * as React from "react"

const COOKIE_MAX_AGE = 60 * 60 * 24 * 30 // 30 days

type UsePercentResizeProps = {
  /** "left" = drag right increases width, "right" = drag left increases width */
  direction: "left" | "right"
  /** Current width in percent (0-100) */
  currentPercent: number
  /** Minimum width in percent */
  minPercent: number
  /** Maximum width in percent */
  maxPercent: number
  /** Callback when percent changes */
  onResize: (percent: number) => void
  /** Cookie name for persistence */
  cookieName?: string
}

export function usePercentResize({
  direction,
  currentPercent,
  minPercent,
  maxPercent,
  onResize,
  cookieName,
}: UsePercentResizeProps) {
  const isDragging = React.useRef(false)
  const startX = React.useRef(0)
  const startPercent = React.useRef(0)
  const viewportWidth = React.useRef(0)
  const lastPercent = React.useRef(currentPercent)

  const onResizeRef = React.useRef(onResize)
  onResizeRef.current = onResize

  const handleMouseDown = React.useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      isDragging.current = true
      startX.current = e.clientX
      startPercent.current = currentPercent
      viewportWidth.current = window.innerWidth

      document.body.style.cursor = "ew-resize"
      document.body.style.userSelect = "none"
    },
    [currentPercent]
  )

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return

      const deltaX = e.clientX - startX.current
      const deltaPercent = (deltaX / viewportWidth.current) * 100

      // Left panel: drag right = increase, Right panel: drag left = increase
      const multiplier = direction === "left" ? 1 : -1
      const newPercent = startPercent.current + deltaPercent * multiplier

      const clampedPercent = Math.max(minPercent, Math.min(maxPercent, newPercent))
      lastPercent.current = clampedPercent
      onResizeRef.current(clampedPercent)
    }

    const handleMouseUp = () => {
      if (!isDragging.current) return
      isDragging.current = false

      document.body.style.cursor = ""
      document.body.style.userSelect = ""

      // Save to cookie
      if (cookieName) {
        document.cookie = `${cookieName}=${lastPercent.current}; path=/; max-age=${COOKIE_MAX_AGE}`
      }
    }

    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", handleMouseUp)

    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
      if (isDragging.current) {
        document.body.style.cursor = ""
        document.body.style.userSelect = ""
      }
    }
  }, [direction, minPercent, maxPercent, cookieName])

  return { handleMouseDown }
}
