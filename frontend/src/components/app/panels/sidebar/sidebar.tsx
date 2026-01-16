"use client"

/**
 * Sidebar — presentational component.
 *
 * Receives all data via props. No logic, no context access.
 * Container handles resize, AppShell provides data.
 */

import {
  LogOutIcon,
  MessageSquareIcon,
  MoonIcon,
  PlusIcon,
  SettingsIcon,
  TrashIcon,
  PanelLeftClose,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  PageHeader,
  PageHeaderLeft,
  PageHeaderRight,
} from "@/components/app/page-header/page-header"
import type { ChatItem } from "@/types/chat"

type SidebarProps = {
  width: number
  onResizeMouseDown?: (e: React.MouseEvent) => void
  // Data
  chats: ChatItem[]
  currentChatId: string | null
  // Actions
  onSelectChat: (id: string) => void
  onNewChat: () => void
  onDeleteChat: (id: string) => void
  onClose: () => void
  onSettings: () => void
  onSignOut: () => void
}

export function Sidebar({
  width,
  onResizeMouseDown,
  chats,
  currentChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  onClose,
  onSettings,
  onSignOut,
}: SidebarProps) {
  return (
    <div
      className="relative flex h-full shrink-0 flex-col bg-sidebar md:min-w-60 md:max-w-96"
      style={{ width }}
    >
      {/* Header */}
      <PageHeader>
        <PageHeaderLeft>
          <span className="text-sm font-semibold">Trading Agent</span>
        </PageHeaderLeft>
        <PageHeaderRight>
          <Button variant="ghost" size="icon-sm" onClick={onNewChat}>
            <PlusIcon />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={onClose}>
            <PanelLeftClose />
          </Button>
        </PageHeaderRight>
      </PageHeader>

      {/* Chat list */}
      <div className="flex-1 overflow-y-auto px-2">
        <div className="py-2">
          <span className="px-2 text-xs font-medium text-muted-foreground">History</span>
        </div>
        {chats.length === 0 ? (
          <div className="px-2 py-4 text-center text-sm text-muted-foreground">
            No chats yet
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {chats.map((chat) => (
              <div
                key={chat.id}
                className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm cursor-pointer hover:bg-accent ${
                  chat.id === currentChatId ? "bg-accent" : ""
                }`}
                onClick={() => onSelectChat(chat.id)}
              >
                <MessageSquareIcon className="size-4 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate">{chat.title}</span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="size-6 opacity-0 group-hover:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation()
                    onDeleteChat(chat.id)
                  }}
                >
                  <TrashIcon className="size-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t px-2 py-2">
        <div className="flex flex-col gap-1">
          <Button
            variant="ghost"
            className="justify-start gap-2 px-2"
            onClick={() => document.documentElement.classList.toggle("dark")}
          >
            <MoonIcon className="size-4" />
            <span>Dark theme</span>
          </Button>
          <Button
            variant="ghost"
            className="justify-start gap-2 px-2"
            onClick={onSettings}
          >
            <SettingsIcon className="size-4" />
            <span>Settings</span>
          </Button>
          <Button
            variant="ghost"
            className="justify-start gap-2 px-2"
            onClick={onSignOut}
          >
            <LogOutIcon className="size-4" />
            <span>Sign out</span>
          </Button>
        </div>
      </div>

      {/* Resize handle - hidden on mobile */}
      {onResizeMouseDown && (
        <div
          onMouseDown={onResizeMouseDown}
          className="absolute top-0 right-0 h-full w-1 cursor-col-resize hover:bg-primary/20"
        />
      )}
    </div>
  )
}
