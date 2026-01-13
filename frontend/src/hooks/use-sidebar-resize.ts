"use client"

import * as React from "react"

type SidebarDirection = "left" | "right"

type UseSidebarResizeProps = {
  direction: SidebarDirection
  minWidth: number
  maxWidth: number
  currentWidth: number
  isCollapsed: boolean
  onResize: (width: number) => void
  onToggle: () => void
  cookieName?: string
  cookieMaxAge?: number
  onDragStart?: () => void
  onDragEnd?: () => void
}

export function useSidebarResize({
  direction,
  minWidth,
  maxWidth,
  currentWidth,
  isCollapsed,
  onResize,
  onToggle,
  cookieName,
  cookieMaxAge = 60 * 60 * 24 * 7,
  onDragStart,
  onDragEnd,
}: UseSidebarResizeProps) {
  const isDragging = React.useRef(false)
  const startX = React.useRef(0)
  const startWidth = React.useRef(0)
  const toggleCooldown = React.useRef(false)

  // Use refs for callbacks to avoid useEffect re-runs
  const onResizeRef = React.useRef(onResize)
  const onToggleRef = React.useRef(onToggle)
  const onDragStartRef = React.useRef(onDragStart)
  const onDragEndRef = React.useRef(onDragEnd)

  // Keep refs updated
  React.useEffect(() => {
    onResizeRef.current = onResize
    onToggleRef.current = onToggle
    onDragStartRef.current = onDragStart
    onDragEndRef.current = onDragEnd
  })

  const handleMouseDown = React.useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      isDragging.current = true
      startX.current = e.clientX
      startWidth.current = isCollapsed ? minWidth : currentWidth

      document.body.style.cursor = "ew-resize"
      document.body.style.userSelect = "none"

      onDragStartRef.current?.()
    },
    [currentWidth, isCollapsed, minWidth]
  )

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return

      const delta = e.clientX - startX.current
      // For left sidebar: moving right increases width
      // For right sidebar: moving left increases width
      const multiplier = direction === "left" ? 1 : -1
      const newWidth = startWidth.current + delta * multiplier

      // Clamp width
      const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth))

      // Auto-collapse threshold (when dragged below 50% of minWidth)
      const collapseThreshold = minWidth * 0.5

      if (newWidth < collapseThreshold && !isCollapsed && !toggleCooldown.current) {
        toggleCooldown.current = true
        onToggleRef.current()
        setTimeout(() => {
          toggleCooldown.current = false
        }, 200)
      } else if (newWidth >= minWidth && isCollapsed && !toggleCooldown.current) {
        toggleCooldown.current = true
        onToggleRef.current()
        setTimeout(() => {
          toggleCooldown.current = false
        }, 200)
      } else if (!isCollapsed) {
        onResizeRef.current(clampedWidth)
      }
    }

    const handleMouseUp = () => {
      if (!isDragging.current) return
      isDragging.current = false

      document.body.style.cursor = ""
      document.body.style.userSelect = ""

      // Save to cookie
      if (cookieName && !isCollapsed) {
        document.cookie = `${cookieName}=${currentWidth}; path=/; max-age=${cookieMaxAge}`
      }

      onDragEndRef.current?.()
    }

    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", handleMouseUp)

    // Cleanup: reset styles if unmounted during drag
    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
      if (isDragging.current) {
        document.body.style.cursor = ""
        document.body.style.userSelect = ""
      }
    }
  }, [direction, minWidth, maxWidth, isCollapsed, currentWidth, cookieName, cookieMaxAge])

  return {
    isDragging,
    handleMouseDown,
  }
}
