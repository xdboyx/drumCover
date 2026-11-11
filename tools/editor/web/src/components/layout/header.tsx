import type { ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { ThemeSwitch } from '@/components/theme-switch'
import { JOB_KIND_LABEL, useJob } from '@/hooks/use-job'
import { cn } from '@/lib/utils'

/** 工作進行中的精簡提示（sidebar 收合時仍看得到） */
function JobPill() {
  const { job } = useJob()
  if (!job || job.state !== 'running' || !job.kind) return null
  return (
    <div
      className="bg-primary/10 text-primary flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
      role="status"
    >
      <Loader2 className="size-3 animate-spin" />
      <span className="hidden sm:inline">
        {JOB_KIND_LABEL[job.kind].running}（{job.project}）
      </span>
      <span className="tabular-nums">{Math.round((job.progress ?? 0) * 100)}%</span>
    </div>
  )
}

/**
 * 頁首：左邊 sidebar 開關 + 標題；`children` 放頁面專屬的工具列（例如編輯器的版本選單）；
 * 右邊固定是工作提示與主題切換。
 */
export function Header({
  title,
  children,
  className,
}: {
  title?: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <header
      className={cn(
        'bg-background/90 sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b px-3 backdrop-blur sm:px-4',
        className
      )}
    >
      <SidebarTrigger className="-ms-1" aria-label="收合或展開側邊欄" />
      <Separator orientation="vertical" className="me-1 h-5" />
      {title && <h1 className="truncate text-base font-semibold">{title}</h1>}
      <div className="flex min-w-0 flex-1 items-center gap-2">{children}</div>
      <div className="flex shrink-0 items-center gap-1">
        <JobPill />
        <ThemeSwitch />
      </div>
    </header>
  )
}
