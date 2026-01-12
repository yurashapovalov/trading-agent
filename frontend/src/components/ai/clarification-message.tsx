"use client"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { HelpCircleIcon } from "lucide-react"
import type { ComponentProps } from "react"

export type ClarificationMessageProps = ComponentProps<"div"> & {
  question: string
  suggestions: string[]
  onSelect: (response: string) => void
}

export function ClarificationMessage({
  question,
  suggestions,
  onSelect,
  className,
  ...props
}: ClarificationMessageProps) {
  return (
    <div
      className={cn(
        "flex w-full max-w-[95%] flex-col gap-3 is-assistant",
        className
      )}
      {...props}
    >
      {/* Question */}
      <div className="flex items-start gap-2 text-sm text-foreground">
        <HelpCircleIcon className="size-4 mt-0.5 text-muted-foreground shrink-0" />
        <span>{question}</span>
      </div>

      {/* Suggestion buttons */}
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 ml-6">
          {suggestions.map((suggestion, index) => (
            <Button
              key={index}
              variant="outline"
              size="sm"
              className="h-auto py-2 px-3 text-sm whitespace-normal text-left"
              onClick={() => onSelect(suggestion)}
            >
              {suggestion}
            </Button>
          ))}
        </div>
      )}

      {/* Hint */}
      <p className="text-xs text-muted-foreground ml-6">
        Выберите вариант или напишите свой ответ
      </p>
    </div>
  )
}
