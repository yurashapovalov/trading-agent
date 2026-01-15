"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
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
        <DialogContent className="sm:max-w-4xl h-[90vh]">
          <DialogHeader>
            <DialogTitle>Processing Steps</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            {steps.map((step, index) => (
              <div key={index} className="text-sm">
                <span className="font-medium">{step.agent}</span>
                {step.durationMs && (
                  <span className="text-muted-foreground ml-2">
                    {step.durationMs}ms
                  </span>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
