"use client"

import { cn } from "@/lib/utils"
import { TableIcon, ChevronRightIcon } from "lucide-react"
import type { DataCard as DataCardType } from "@/types/chat"
import type { HTMLAttributes } from "react"

export type DataCardProps = HTMLAttributes<HTMLDivElement> & {
  data: DataCardType
  onClick?: () => void
}

export function DataCard({
  data,
  onClick,
  className,
  ...props
}: DataCardProps) {
  const { title } = data

  return (
    <div
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={onClick ? (e) => e.key === "Enter" && onClick() : undefined}
      className={cn(
        "my-3 flex items-center gap-2 rounded-lg border bg-muted/50 px-4 py-3",
        onClick && "cursor-pointer hover:bg-muted/80 transition-colors",
        className
      )}
      {...props}
    >
      <TableIcon className="size-4 text-muted-foreground" />
      <span className="flex-1 font-medium text-sm">{title || "Data"}</span>
      {onClick && <ChevronRightIcon className="size-4 text-muted-foreground" />}
    </div>
  )
}
