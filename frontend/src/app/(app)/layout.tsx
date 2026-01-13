import { cookies } from "next/headers"
import { LeftPanelContainer } from "@/components/app/left-panel/left-panel.container"
import { RightPanelContainer } from "@/components/app/right-panel/right-panel.container"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"

export default async function Layout({
  children,
}: {
  children: React.ReactNode
}) {
  const cookieStore = await cookies()
  const defaultLeftOpen = cookieStore.get("sidebar_left")?.value !== "false"
  const defaultRightOpen = cookieStore.get("sidebar_right")?.value === "true"

  // Read saved widths from cookies
  const leftWidthCookie = cookieStore.get("sidebar_left_width")?.value
  const rightWidthCookie = cookieStore.get("sidebar_right_width")?.value
  const defaultLeftWidth = leftWidthCookie ? parseInt(leftWidthCookie, 10) : undefined
  const defaultRightWidth = rightWidthCookie ? parseInt(rightWidthCookie, 10) : undefined

  return (
    <SidebarProvider
      defaultOpen={defaultLeftOpen}
      defaultRightOpen={defaultRightOpen}
      {...(defaultLeftWidth && { defaultLeftWidth })}
      {...(defaultRightWidth && { defaultRightWidth })}
    >
      <LeftPanelContainer />
      <SidebarInset className="overflow-hidden">
        {children}
      </SidebarInset>
      <RightPanelContainer />
    </SidebarProvider>
  )
}
