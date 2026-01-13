type PageHeaderProps = {
  title: string
  subtitle?: string
  leftAction?: React.ReactNode
  rightAction?: React.ReactNode
}

export function PageHeader({
  title,
  subtitle,
  leftAction,
  rightAction,
}: PageHeaderProps) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 px-4">
      {leftAction}
      <h1 className="text-sm font-medium">{title}</h1>
      <div className="ml-auto flex items-center gap-3">
        {subtitle && (
          <span className="text-xs text-muted-foreground">{subtitle}</span>
        )}
        {rightAction}
      </div>
    </header>
  )
}
