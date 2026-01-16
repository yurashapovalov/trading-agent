"use client"

/**
 * Hook for pixel-based panel resize.
 *
 * Converts mouse drag to pixel width change.
 * Saves to cookie on drag end.
 */

import * as React from "react"

const COOKIE_MAX_AGE = 60 * 60 * 24 * 30 // 30 days

type UsePixelResizeProps = {
  /** "left" = drag right increases width, "right" = drag left increases width */
  direction: "left" | "right"
  /** Current width in pixels */
  currentWidth: number
  /** Minimum width in pixels */
  minWidth: number
  /** Maximum width in pixels */
  maxWidth: number
  /** Callback when width changes */
  onResize: (width: number) => void
  /** Cookie name for persistence */
  cookieName?: string
}

export function usePixelResize({
  direction,
  currentWidth,
  minWidth,
  maxWidth,
  onResize,
  cookieName,
}: UsePixelResizeProps) {
  const isDragging = React.useRef(false)
  const startX = React.useRef(0)
  const startWidth = React.useRef(0)
  const lastWidth = React.useRef(currentWidth)

  const onResizeRef = React.useRef(onResize)
  onResizeRef.current = onResize

  const handleMouseDown = React.useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      isDragging.current = true
      startX.current = e.clientX
      startWidth.current = currentWidth

      document.body.style.cursor = "ew-resize"
      document.body.style.userSelect = "none"
    },
    [currentWidth]
  )

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return

      const deltaX = e.clientX - startX.current

      // Left panel: drag right = increase, Right panel: drag left = increase
      const multiplier = direction === "left" ? 1 : -1
      const newWidth = startWidth.current + deltaX * multiplier

      const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth))
      lastWidth.current = clampedWidth
      onResizeRef.current(clampedWidth)
    }

    const handleMouseUp = () => {
      if (!isDragging.current) return
      isDragging.current = false

      document.body.style.cursor = ""
      document.body.style.userSelect = ""

      // Save to cookie
      if (cookieName) {
        document.cookie = `${cookieName}=${lastWidth.current}; path=/; max-age=${COOKIE_MAX_AGE}`
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
  }, [direction, minWidth, maxWidth, cookieName])

  return { handleMouseDown }
}
