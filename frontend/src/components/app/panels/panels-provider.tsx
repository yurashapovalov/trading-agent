"use client"

/**
 * Panels state management.
 *
 * Single source of truth for panel dimensions and constraints.
 * Containers get all values from here — no hardcoded constants elsewhere.
 * Reads initial sizes from cookies for persistence.
 */

import { createContext, useContext, useState, useMemo, useEffect, type ReactNode } from "react"

// Left panel constraints (pixels) — Tailwind: min-w-60, max-w-96
const LEFT_MIN_WIDTH = 240
const LEFT_MAX_WIDTH = 384
const LEFT_DEFAULT_WIDTH = 260

// Right panel constraints (percent)
const RIGHT_MIN_PERCENT = 30
const RIGHT_MAX_PERCENT = 70
const RIGHT_DEFAULT_PERCENT = 50

// Breakpoints (matches Tailwind)
const BREAKPOINT_MD = 768
const BREAKPOINT_LG = 1024

// Cookie names
export const COOKIE_LEFT_WIDTH = "panel_left_width"
export const COOKIE_RIGHT_PERCENT = "panel_right_percent"

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`))
  return match ? match[2] : null
}

function getInitialLeftWidth(): number {
  const cookie = getCookie(COOKIE_LEFT_WIDTH)
  if (cookie) {
    const value = parseInt(cookie, 10)
    if (!isNaN(value) && value >= LEFT_MIN_WIDTH && value <= LEFT_MAX_WIDTH) {
      return value
    }
  }
  return LEFT_DEFAULT_WIDTH
}

function getInitialRightPercent(): number {
  const cookie = getCookie(COOKIE_RIGHT_PERCENT)
  if (cookie) {
    const value = parseFloat(cookie)
    if (!isNaN(value) && value >= RIGHT_MIN_PERCENT && value <= RIGHT_MAX_PERCENT) {
      return value
    }
  }
  return RIGHT_DEFAULT_PERCENT
}

type PanelsContextType = {
  // Left panel (pixels)
  leftOpen: boolean
  setLeftOpen: (open: boolean) => void
  leftWidth: number
  setLeftWidth: (width: number) => void
  leftMinWidth: number
  leftMaxWidth: number

  // Right panel (percent)
  rightOpen: boolean
  setRightOpen: (open: boolean) => void
  rightWidthPercent: number
  setRightWidthPercent: (percent: number) => void
  rightMinPercent: number
  rightMaxPercent: number

  // Responsive
  isMobile: boolean
}

const PanelsContext = createContext<PanelsContextType | null>(null)

export function usePanels() {
  const context = useContext(PanelsContext)
  if (!context) {
    throw new Error("usePanels must be used within PanelsProvider")
  }
  return context
}

type PanelsProviderProps = {
  children: ReactNode
  defaultLeftOpen?: boolean
  defaultRightOpen?: boolean
}

export function PanelsProvider({
  children,
  defaultLeftOpen = true,
  defaultRightOpen = true,
}: PanelsProviderProps) {
  const [leftOpen, setLeftOpen] = useState(defaultLeftOpen)
  const [rightOpen, setRightOpen] = useState(defaultRightOpen)
  const [leftWidth, setLeftWidth] = useState(getInitialLeftWidth)
  const [rightWidthPercent, setRightWidthPercent] = useState(getInitialRightPercent)
  const [isMobile, setIsMobile] = useState(false)

  // Responsive: auto-hide panels on smaller screens
  useEffect(() => {
    let wasMobile = window.innerWidth < BREAKPOINT_MD
    let wasTablet = window.innerWidth < BREAKPOINT_LG

    const handleResize = () => {
      const width = window.innerWidth
      const mobile = width < BREAKPOINT_MD
      const tablet = width < BREAKPOINT_LG

      setIsMobile(mobile)

      // Only close panels on TRANSITION to smaller screen
      if (mobile && !wasMobile) {
        // Transitioning to mobile: hide both panels
        setLeftOpen(false)
        setRightOpen(false)
      } else if (tablet && !wasTablet && !mobile) {
        // Transitioning to tablet (but not mobile): hide right panel only
        setRightOpen(false)
      }

      wasMobile = mobile
      wasTablet = tablet
    }

    // Initial state
    setIsMobile(wasMobile)
    if (wasMobile) {
      setLeftOpen(false)
      setRightOpen(false)
    } else if (wasTablet) {
      setRightOpen(false)
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  const value = useMemo(
    () => ({
      leftOpen,
      setLeftOpen,
      leftWidth,
      setLeftWidth,
      leftMinWidth: LEFT_MIN_WIDTH,
      leftMaxWidth: LEFT_MAX_WIDTH,

      rightOpen,
      setRightOpen,
      rightWidthPercent,
      setRightWidthPercent,
      rightMinPercent: RIGHT_MIN_PERCENT,
      rightMaxPercent: RIGHT_MAX_PERCENT,

      isMobile,
    }),
    [leftOpen, leftWidth, rightOpen, rightWidthPercent, isMobile]
  )

  return (
    <PanelsContext.Provider value={value}>
      {children}
    </PanelsContext.Provider>
  )
}
