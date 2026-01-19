"use client"

import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { TableIcon, BarChart3Icon, DownloadIcon } from "lucide-react"
import type { DataCard as DataCardType } from "@/types/chat"
import type { HTMLAttributes } from "react"

export type DataCardProps = HTMLAttributes<HTMLDivElement> & {
  data: DataCardType
  showAnalyzeButton?: boolean
  onAnalyze?: () => void
}

export function DataCard({
  data,
  showAnalyzeButton = false,
  onAnalyze,
  className,
  ...props
}: DataCardProps) {
  const { title, row_count, data: tableData } = data
  const rows = (tableData as any)?.rows || []
  const columns = (tableData as any)?.columns || Object.keys(rows[0] || {})

  // Format cell value for display
  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return "—"
    if (typeof value === "number") {
      // Format numbers nicely
      if (Number.isInteger(value)) return value.toLocaleString()
      return value.toLocaleString(undefined, { maximumFractionDigits: 4 })
    }
    return String(value)
  }

  return (
    <Card className={cn("my-3", className)} {...props}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <TableIcon className="size-4 text-muted-foreground" />
          <CardTitle className="text-base">{title || "Data"}</CardTitle>
        </div>
        <CardDescription>
          {row_count} {row_count === 1 ? "row" : "rows"}
        </CardDescription>
      </CardHeader>

      {rows.length > 0 && (
        <CardContent className="pb-3">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  {columns.map((col: string) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left font-medium text-muted-foreground"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 10).map((row: Record<string, unknown>, i: number) => (
                  <tr key={i} className="border-b last:border-0">
                    {columns.map((col: string) => (
                      <td key={col} className="px-3 py-2 font-mono">
                        {formatValue(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
                {rows.length > 10 && (
                  <tr>
                    <td
                      colSpan={columns.length}
                      className="px-3 py-2 text-center text-muted-foreground"
                    >
                      ... and {rows.length - 10} more rows
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      )}

      {showAnalyzeButton && (
        <CardFooter className="pt-0">
          <Button
            variant="outline"
            size="sm"
            onClick={onAnalyze}
            className="gap-2"
          >
            <BarChart3Icon className="size-4" />
            Analyze
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}
