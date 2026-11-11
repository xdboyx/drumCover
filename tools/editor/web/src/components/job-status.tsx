import { AlertCircle, CheckCircle2, Loader2, Moon } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import { ErrorDetails } from '@/components/error-details'
import { JobSteps } from '@/components/job-steps'
import { JOB_KIND_LABEL, useJob } from '@/hooks/use-job'

/** 全域工作狀態：種類、專案、步驟、進度條；失敗時顯示錯誤訊息。放在 sidebar 或 header。 */
export function JobStatusPanel() {
  const { job } = useJob()
  if (!job) return null
  const kind = job.kind

  if (job.state === 'idle' || !kind) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-xs">
        <Moon className="size-3.5" />
        目前沒有工作
      </div>
    )
  }

  if (job.state === 'running') {
    return (
      <div className="space-y-2" role="status" aria-live="polite">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Loader2 className="text-primary size-4 animate-spin" />
          {JOB_KIND_LABEL[kind].running}
        </div>
        <div className="text-muted-foreground truncate text-xs" title={job.project}>
          專案：{job.project}
        </div>
        <JobSteps
          steps={job.steps ?? []}
          index={job.step_index ?? 0}
          progress={job.progress ?? 0}
        />
        <Progress value={Math.round((job.progress ?? 0) * 100)} className="h-1.5" />
      </div>
    )
  }

  if (job.state === 'error') {
    const failedStep = job.failed_step != null ? job.steps?.[job.failed_step] : undefined
    return (
      <div className="space-y-1.5" role="alert">
        <div className="text-destructive flex items-center gap-2 text-sm font-medium">
          <AlertCircle className="size-4" />
          {JOB_KIND_LABEL[kind].failed}
        </div>
        <div className="text-muted-foreground truncate text-xs" title={job.project}>
          專案：{job.project}
          {failedStep ? `・步驟「${failedStep}」` : ''}
        </div>
        {job.error && <ErrorDetails message={job.error} className="text-xs" />}
      </div>
    )
  }

  return (
    <div className="space-y-1" role="status">
      <div className="text-success flex items-center gap-2 text-sm font-medium">
        <CheckCircle2 className="size-4" />
        {kind === 'render' ? '輸出完成' : kind === 'reimport' ? '重新扒譜完成' : '扒譜完成'}
      </div>
      <div className="text-muted-foreground truncate text-xs" title={job.project}>
        專案：{job.project}
      </div>
      {job.output && (
        <div className="text-muted-foreground font-mono text-[11px] break-all">
          projects/{job.project}/{job.output}
        </div>
      )}
    </div>
  )
}
