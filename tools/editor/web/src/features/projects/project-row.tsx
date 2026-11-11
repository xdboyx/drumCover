import { Link } from '@tanstack/react-router'
import { ChevronRight, Music2, RotateCcw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ErrorDetails } from '@/components/error-details'
import { JobSteps } from '@/components/job-steps'
import { cn } from '@/lib/utils'
import type { JobStatus, ProjectListItem } from '@/lib/types'
import { formatRelative, projectMeta } from './lib/format'

/**
 * 專案清單的一列。已扒完的專案整列可點（名稱是「延伸到整列」的連結，Tab 可聚焦、Enter 開啟編輯器）；
 * 扒譜中、失敗的專案不能開啟，改顯示進度或錯誤與重試。
 * 列尾只放次要動作（重試是 outline），不放實心按鈕。
 */
export function ProjectRow({
  p,
  job,
  busy,
  onRetry,
  compact,
}: {
  p: ProjectListItem
  job?: JobStatus
  busy: boolean
  onRetry?: (name: string) => void
  /** 首頁「最近的專案」用：只顯示辨識資訊，不顯示錯誤與重試 */
  compact?: boolean
}) {
  const ready = p.status === 'ready'
  const reimportFailed = ready && !!p.reimport_error
  const meta = projectMeta(p)
  const updated = formatRelative(p.updated)
  const retryStep = p.status === 'failed' ? p.failed_step : p.reimport_failed_step
  const progress = job?.progress ?? p.progress ?? 0

  const title = (
    <span className="truncate font-medium" title={p.name}>
      {p.name}
    </span>
  )

  return (
    <li
      className={cn(
        'group relative flex items-start gap-3 px-4 py-3 transition-colors',
        ready && 'hover:bg-accent/60 focus-within:bg-accent/60'
      )}
    >
      <div className="bg-muted text-muted-foreground mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md">
        <Music2 className="size-4" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          {ready ? (
            <Link
              to="/editor"
              search={{ p: p.name }}
              className="focus-visible:after:ring-ring flex min-w-0 rounded-sm outline-none after:absolute after:inset-0 after:content-[''] focus-visible:after:ring-2 focus-visible:after:ring-inset"
              aria-label={`開啟專案「${p.name}」的編輯器`}
            >
              {title}
            </Link>
          ) : (
            title
          )}
          {p.status === 'running' && (
            <Badge variant="secondary" className="bg-primary/10 text-primary">
              {job?.kind === 'reimport' ? '重新扒譜中' : '扒譜中'}
            </Badge>
          )}
          {p.status === 'failed' && <Badge variant="destructive">扒譜失敗</Badge>}
          {reimportFailed && <Badge variant="destructive">重新扒譜失敗</Badge>}
        </div>

        {ready && (meta.length > 0 || updated) && (
          <p className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs">
            {meta.map((m, i) => (
              <span key={m} className="flex items-center gap-1.5">
                {i > 0 && <span aria-hidden>・</span>}
                {m}
              </span>
            ))}
            {updated && (
              <span className="flex items-center gap-1.5">
                {meta.length > 0 && <span aria-hidden>・</span>}
                更新於 {updated}
              </span>
            )}
          </p>
        )}

        {!compact && p.status === 'running' && (
          <div className="mt-2 grid max-w-md gap-2">
            {job?.steps && (
              <JobSteps steps={job.steps} index={job.step_index ?? 0} progress={progress} />
            )}
            <Progress value={Math.round(progress * 100)} className="h-1.5" />
          </div>
        )}
        {!compact && p.status === 'failed' && (
          <ErrorDetails
            className="mt-2"
            prefix={p.failed_step ? `失敗在「${p.failed_step}」這一步` : undefined}
            message={p.error ?? ''}
          />
        )}
        {!compact && reimportFailed && (
          <ErrorDetails
            className="mt-2"
            prefix={
              p.reimport_failed_step ? `重新扒譜失敗在「${p.reimport_failed_step}」這一步` : undefined
            }
            message={p.reimport_error ?? ''}
          />
        )}
      </div>

      <div className="relative z-10 flex shrink-0 items-center gap-2 self-center">
        {!compact && (p.status === 'failed' || reimportFailed) && onRetry && (
          <Button
            variant="outline"
            size="sm"
            disabled={busy}
            title={busy ? '同時只能跑一個工作，請等目前的工作結束' : undefined}
            onClick={() => onRetry(p.name)}
          >
            <RotateCcw />
            {retryStep ? `從「${retryStep}」重試` : '重試'}
          </Button>
        )}
        {ready && (
          <span
            aria-hidden
            className="text-muted-foreground group-hover:text-foreground pointer-events-none flex items-center text-sm transition-colors"
          >
            <span className="hidden sm:inline">開啟</span>
            <ChevronRight className="size-4" />
          </span>
        )}
      </div>
    </li>
  )
}
