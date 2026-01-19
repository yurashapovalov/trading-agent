"use client"

import { cn } from "@/lib/utils"
import { TableIcon } from "lucide-react"
import type { DataCard as DataCardType } from "@/types/chat"
import type { HTMLAttributes } from "react"

export type DataCardProps = HTMLAttributes<HTMLDivElement> & {
  data: DataCardType
}

export function DataCard({
  data,
  className,
  ...props
}: DataCardProps) {
  const { title } = data

  return (
    <div
      className={cn(
        "my-3 flex items-center gap-2 rounded-lg border bg-muted/50 px-4 py-3",
        className
      )}
      {...props}
    >
      <TableIcon className="size-4 text-muted-foreground" />
      <span className="font-medium text-sm">{title || "Data"}</span>
    </div>
  )
}
