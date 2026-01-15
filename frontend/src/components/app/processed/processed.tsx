"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
} from "@/components/ui/dialog"
import { ChevronRightIcon } from "lucide-react"

import type { AgentStep } from "@/types/chat"

type ProcessedProps = {
  steps: AgentStep[]
  isLoading: boolean
}

export function Processed({ steps, isLoading }: ProcessedProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="w-full">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        {isLoading ? "Thinking..." : "Done"}
        {!isLoading && <ChevronRightIcon className="size-4" />}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-4xl h-[90vh] overflow-y-auto content-start">
          <DialogHeader>
            <h2 className="text-xl leading-none font-semibold">Processing Steps</h2>
          </DialogHeader>
          <div className="grid gap-4">
            {steps.map((step, index) => (
              <div key={index}>
                <h3 className="text-lg leading-none font-semibold capitalize">{index + 1}. {step.agent}</h3>
                {step.durationMs && (
                  <div className="text-sm text-muted-foreground mt-1">
                    {step.durationMs}ms
                  </div>
                )}
                {step.result && (
                  <pre className="text-xs mt-2 overflow-x-auto">
                    {JSON.stringify(step.result, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
