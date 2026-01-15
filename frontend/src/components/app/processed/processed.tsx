"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion"
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
            <DialogTitle className="text-xl">Processing Steps</DialogTitle>
          </DialogHeader>
          <Accordion type="multiple" className="w-full">
            {steps.map((step, index) => (
              <AccordionItem key={index} value={`step-${index}`}>
                <AccordionTrigger className="text-lg font-semibold capitalize hover:no-underline">
                  {index + 1}. {step.agent}
                  {step.durationMs && (
                    <span className="text-sm text-muted-foreground font-normal ml-2">
                      {step.durationMs}ms
                    </span>
                  )}
                </AccordionTrigger>
                <AccordionContent>
                  {step.result && (
                    <pre className="text-xs whitespace-pre-wrap break-words">
                      {JSON.stringify(step.result, null, 2)}
                    </pre>
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </DialogContent>
      </Dialog>
    </div>
  )
}
