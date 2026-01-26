"use client"

/**
 * SidebarItem — presentational component for sidebar list items.
 *
 * Dumb component, just renders UI with props.
 */

import type { LucideIcon } from "lucide-react"
import { TrashIcon } from "lucide-react"
import { Button } from "@/components/ui/button"

type SidebarItemProps = {
  icon: LucideIcon
  label: string
  onClick: () => void
  isActive?: boolean
  onDelete?: () => void
}

export function SidebarItem({
  icon: Icon,
  label,
  onClick,
  isActive = false,
  onDelete,
}: SidebarItemProps) {
  return (
    <div
      className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm cursor-pointer hover:bg-accent ${
        isActive ? "bg-accent" : ""
      }`}
      onClick={onClick}
    >
      <Icon className="size-4 shrink-0 text-muted-foreground" />
      <span className="flex-1 truncate">{label}</span>
      {onDelete && (
        <Button
          variant="ghost"
          size="icon-sm"
          className="size-6 opacity-0 group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
        >
          <TrashIcon className="size-3" />
        </Button>
      )}
    </div>
  )
}
