/**
 * PageHeader — flexible header with three slots.
 *
 * ┌─────────────┬────────────────────────┬─────────────┐
 * │    Left     │        Center          │    Right    │
 * │ (btn/text)  │    (flex-1, text)      │  (buttons)  │
 * └─────────────┴────────────────────────┴─────────────┘
 *
 * Usage:
 *   <PageHeader>
 *     <PageHeaderLeft>
 *       <Button />
 *       <span>Title</span>
 *     </PageHeaderLeft>
 *     <PageHeaderCenter>
 *       <span>Status</span>
 *     </PageHeaderCenter>
 *     <PageHeaderRight>
 *       <Button />
 *       <Button />
 *     </PageHeaderRight>
 *   </PageHeader>
 */

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

type PageHeaderProps = {
  children: ReactNode
  className?: string
}

export function PageHeader({ children, className }: PageHeaderProps) {
  return (
    <header className={cn("flex h-12 shrink-0 items-center justify-between gap-2 px-4", className)}>
      {children}
    </header>
  )
}

type SlotProps = {
  children?: ReactNode
  className?: string
}

export function PageHeaderLeft({ children, className }: SlotProps) {
  return (
    <div className={cn("flex shrink-0 items-center gap-2", className)}>
      {children}
    </div>
  )
}

export function PageHeaderCenter({ children, className }: SlotProps) {
  return (
    <div className={cn("flex flex-1 items-center justify-center", className)}>
      {children}
    </div>
  )
}

export function PageHeaderRight({ children, className }: SlotProps) {
  return (
    <div className={cn("flex shrink-0 items-center gap-1", className)}>
      {children}
    </div>
  )
}
