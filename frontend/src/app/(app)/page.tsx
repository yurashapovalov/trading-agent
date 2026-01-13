"use client"

import dynamic from "next/dynamic"

const ChatPanel = dynamic(() => import("@/components/app/chat-panel/chat-panel.container"), {
  ssr: false,
  loading: () => (
    <div className="flex h-dvh items-center justify-center">
      <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
    </div>
  ),
})

export default function Page() {
  return <ChatPanel />
}
