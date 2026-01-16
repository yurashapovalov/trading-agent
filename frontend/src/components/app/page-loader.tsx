/**
 * Full-page loading spinner for lazy-loaded components.
 */

import { Spinner } from "@/components/ui/spinner"

export function PageLoader() {
  return (
    <div className="flex h-dvh items-center justify-center">
      <Spinner className="size-8" />
    </div>
  )
}
