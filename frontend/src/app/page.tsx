"use client"

import dynamic from "next/dynamic"

const Chat = dynamic(() => import("@/components/chat"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center">
      <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
    </div>
  ),
})

export default function Page() {
  return <Chat />
}
