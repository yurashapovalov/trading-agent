"use client"

/**
 * ContextPanelContainer — logic layer for ContextPanel.
 *
 * Handles:
 * - Resize behavior (usePanels + usePercentResize)
 * - Open/close state
 * - Mobile: change body background when open
 * - Fetching data from API when opened
 *
 * Data comes from AppShell via props (DataCard with request_id).
 */

import { useEffect, useState } from "react"
import { usePanels, COOKIE_RIGHT_PERCENT } from "../panels-provider"
import { usePercentResize } from "@/hooks/use-percent-resize"
import { ContextPanel } from "./context-panel"
import { useAuth } from "@/providers"
import type { DataCard } from "@/types/chat"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

type ContextPanelContainerProps = {
  data: DataCard | null
}

type LoadedData = {
  rows: Record<string, unknown>[]
  columns: string[]
  row_count: number
  title: string
}

export function ContextPanelContainer({ data }: ContextPanelContainerProps) {
  const { session } = useAuth()
  const [loadedData, setLoadedData] = useState<LoadedData | null>(null)
  const [isLoadingData, setIsLoadingData] = useState(false)
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

  // Load data from API when data card changes
  useEffect(() => {
    if (!data?.request_id || !session?.access_token) {
      setLoadedData(null)
      return
    }

    const loadData = async () => {
      setIsLoadingData(true)
      try {
        const response = await fetch(`${API_URL}/chat/data/${data.request_id}`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        })
        if (response.ok) {
          const result = await response.json()
          setLoadedData(result)
        } else {
          setLoadedData(null)
        }
      } catch (e) {
        console.error("Failed to load data:", e)
        setLoadedData(null)
      } finally {
        setIsLoadingData(false)
      }
    }

    loadData()
  }, [data?.request_id, session?.access_token])

  if (!rightOpen) return null

  return (
    <ContextPanel
      widthPercent={isMobile ? 100 : rightWidthPercent}
      onResizeMouseDown={isMobile ? undefined : handleMouseDown}
      onClose={() => setRightOpen(false)}
      isMobile={isMobile}
      title={data?.title || loadedData?.title || "Data"}
      rowCount={data?.row_count || loadedData?.row_count || 0}
      rows={loadedData?.rows || []}
      columns={loadedData?.columns || []}
      isLoading={isLoadingData}
    />
  )
}
