"use client"

/**
 * ContextPanel — presentational component.
 *
 * Receives all data via props. No logic, no context access.
 * Container handles resize, AppShell provides data.
 */

import { X, TableIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  PageHeader,
  PageHeaderLeft,
  PageHeaderRight,
} from "@/components/app/page-header/page-header"
import type { DataCard } from "@/types/chat"

type ContextPanelProps = {
  /** Width in percent (0-100) */
  widthPercent: number
  onResizeMouseDown?: (e: React.MouseEvent) => void
  // Actions
  onClose: () => void
  isMobile?: boolean
  // Data
  data: DataCard | null
}

export function ContextPanel({
  widthPercent,
  onResizeMouseDown,
  onClose,
  isMobile,
  data,
}: ContextPanelProps) {
  // Debug: log incoming data structure
  console.log("[ContextPanel] data:", data)
  console.log("[ContextPanel] data.data:", data?.data)

  // Extract rows and columns from data
  const dataObj = data?.data as { rows?: Record<string, unknown>[]; columns?: string[] } | undefined
  const rows = dataObj?.rows || []
  const columns = dataObj?.columns || (rows.length > 0 ? Object.keys(rows[0]) : [])

  console.log("[ContextPanel] rows:", rows.length, "columns:", columns)

  return (
    <div
      className={`relative flex h-full shrink-0 flex-col ${isMobile ? 'w-screen' : 'min-w-[30%] max-w-[70%]'}`}
      style={isMobile ? { backgroundColor: 'var(--bg-primary)' } : { width: `${widthPercent}%`, backgroundColor: 'var(--bg-primary)' }}
    >
      {/* Resize handle - hidden on mobile */}
      {onResizeMouseDown && (
        <div
          onMouseDown={onResizeMouseDown}
          className="absolute top-0 left-0 h-full w-1 cursor-col-resize hover:bg-primary/20"
        />
      )}

      {/* Header */}
      <PageHeader>
        <PageHeaderLeft>
          <TableIcon className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold">{data?.title || "Data"}</span>
        </PageHeaderLeft>
        <PageHeaderRight>
          <span className="text-xs text-muted-foreground">{data?.row_count || 0} rows</span>
          <Button variant="ghost" size="icon-sm" onClick={onClose}>
            <X />
          </Button>
        </PageHeaderRight>
      </PageHeader>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {rows.length > 0 ? (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-[var(--bg-primary)]">
              <tr className="border-b">
                {columns.map((col) => (
                  <th key={col} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b hover:bg-muted/50">
                  {columns.map((col) => (
                    <td key={col} className="px-3 py-2 whitespace-nowrap">
                      {formatCellValue(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            No data to display
          </div>
        )}
      </div>
    </div>
  )
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toLocaleString()
    return value.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }
  return String(value)
}
