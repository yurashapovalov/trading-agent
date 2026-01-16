"use client"

/**
 * ContextPanel — presentational component.
 *
 * Receives all data via props. No logic, no context access.
 * Container handles resize, AppShell provides data.
 */

import { X, PinIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  PageHeader,
  PageHeaderLeft,
  PageHeaderRight,
} from "@/components/app/page-header/page-header"

type ContextPanelProps = {
  /** Width in percent (0-100) */
  widthPercent: number
  onResizeMouseDown?: (e: React.MouseEvent) => void
  // Actions
  onClose: () => void
  isMobile?: boolean
}

export function ContextPanel({
  widthPercent,
  onResizeMouseDown,
  onClose,
  isMobile,
}: ContextPanelProps) {
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
          <span className="text-sm font-semibold">Context</span>
        </PageHeaderLeft>
        <PageHeaderRight>
          <Button variant="ghost" size="icon-sm" onClick={onClose}>
            <X />
          </Button>
        </PageHeaderRight>
      </PageHeader>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="rounded-lg border p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <PinIcon className="size-3" />
            <span>Context data will appear here</span>
          </div>
        </div>
      </div>
    </div>
  )
}
