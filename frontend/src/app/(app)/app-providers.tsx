"use client"

import type { ReactNode } from "react"
import { SidebarProvider } from "@/components/ui/sidebar"
import { ChatsProvider } from "@/components/chats-provider"

type AppProvidersProps = {
  children: ReactNode
  defaultLeftOpen: boolean
  defaultRightOpen: boolean
  defaultLeftWidth?: number
  defaultRightWidth?: number
}

export function AppProviders({
  children,
  defaultLeftOpen,
  defaultRightOpen,
  defaultLeftWidth,
  defaultRightWidth,
}: AppProvidersProps) {
  return (
    <ChatsProvider>
      <SidebarProvider
        defaultOpen={defaultLeftOpen}
        defaultRightOpen={defaultRightOpen}
        {...(defaultLeftWidth && { defaultLeftWidth })}
        {...(defaultRightWidth && { defaultRightWidth })}
      >
        {children}
      </SidebarProvider>
    </ChatsProvider>
  )
}
