import { PinIcon, XIcon } from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"

type PinnedItem = {
  id: string
  content: string
}

type Artifact = {
  id: string
  title: string
  type: string
}

type RightPanelProps = {
  pinnedItems: PinnedItem[]
  artifacts: Artifact[]
  onClose: () => void
  onSelectPinned: (id: string) => void
  onSelectArtifact: (id: string) => void
}

export function RightPanel({
  pinnedItems,
  artifacts,
  onClose,
}: RightPanelProps) {
  return (
    <Sidebar side="right" collapsible="offcanvas" className="bg-background">
      <SidebarHeader>
        <div className="flex items-center justify-between px-2">
          <span className="font-semibold">Artifacts</span>
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
      </SidebarHeader>
      <SidebarContent>
        <div className="p-4 space-y-4">
          {pinnedItems.length > 0 ? (
            pinnedItems.map((item) => (
              <div key={item.id} className="rounded-lg border p-4">
                <div className="flex items-center gap-2 text-sm">
                  <PinIcon className="size-3" />
                  <span>{item.content}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-lg border p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <PinIcon className="size-3" />
                <span>Pinned messages will appear here</span>
              </div>
            </div>
          )}
          {artifacts.length === 0 && (
            <div className="text-center text-sm text-muted-foreground">
              No artifacts yet
            </div>
          )}
        </div>
      </SidebarContent>
      <SidebarRail side="right" />
    </Sidebar>
  )
}
