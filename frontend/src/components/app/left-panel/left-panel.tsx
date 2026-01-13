import {
  LogOutIcon,
  MessageSquareIcon,
  PlusIcon,
  SettingsIcon,
  XIcon,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"

type HistoryItem = {
  id: string
  title: string
}

type LeftPanelProps = {
  history: HistoryItem[]
  onClose: () => void
  onNewChat: () => void
  onSelectChat: (id: string) => void
  onSettings: () => void
  onSignOut: () => void
}

export function LeftPanel({
  history,
  onClose,
  onNewChat,
  onSelectChat,
  onSettings,
  onSignOut,
}: LeftPanelProps) {
  return (
    <Sidebar>
      <SidebarHeader>
        <div className="flex items-center justify-between px-2">
          <span className="font-semibold">Trading Agent</span>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="size-7" onClick={onNewChat}>
              <PlusIcon className="size-4" />
              <span className="sr-only">New Chat</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={onClose}
            >
              <XIcon className="size-4" />
              <span className="sr-only">Close</span>
            </Button>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>History</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {history.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton onClick={() => onSelectChat(item.id)}>
                    <MessageSquareIcon />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={onSettings}>
              <SettingsIcon />
              <span>Settings</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={onSignOut}>
              <LogOutIcon />
              <span>Sign out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail side="left" />
    </Sidebar>
  )
}
