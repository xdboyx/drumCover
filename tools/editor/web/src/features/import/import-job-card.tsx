import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { AlertCircle, CheckCircle2, FolderOpen, Loader2, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ErrorDetails } from '@/components/error-details'
import { JobSteps } from '@/components/job-steps'
import { useRefreshJob } from '@/hooks/use-job'
import * as api from '@/lib/api'
import type { JobStatus } from '@/lib/types'
import { overallProgress } from './lib/job-progress'
import { resultKey, useImportUi } from './store'

/**
 * 首頁在表單位置顯示「扒譜工作」的狀態：
 * 進行中＝步驟與進度；完成＝開啟編輯器（本畫面唯一的實心按鈕）；失敗＝原因與從失敗步驟重試。
 * 後端沒有取消工作的 API，所以進行中不提供取消，只說明可以離開、進度會保留。
 */
export function ImportJobCard({ job }: { job: JobStatus }) {
  const project = job.project ?? ''
  const refresh = useRefreshJob()
  const { dismiss, reset } = useImportUi()
  const [retrying, setRetrying] = useState(false)

  async function retry() {
    setRetrying(true)
    reset()
    try {
      await api.projectRetry(project)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setRetrying(false)
      refresh()
    }
  }

  const anotherButton = (label: string) => (
    <Button variant="outline" onClick={() => dismiss(resultKey(project, job.state))}>
      {label}
    </Button>
  )

  if (job.state === 'running') {
    const pct = Math.round(overallProgress(job) * 100)
    const steps = job.steps ?? []
    const idx = job.step_index ?? 0
    return (
      <Card role="status" aria-live="polite">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Loader2 className="text-primary size-5 animate-spin" />
            正在扒譜
          </CardTitle>
          <CardDescription className="truncate" title={project}>
            專案：{project}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium">
                {steps.length > 0
                  ? `第 ${Math.min(idx + 1, steps.length)} / ${steps.length} 步：${job.step ?? steps[idx] ?? ''}`
                  : '處理中'}
              </span>
              <span className="text-muted-foreground tabular-nums">整體 {pct}%</span>
            </div>
            <Progress value={pct} aria-label="整體進度" />
          </div>
          <JobSteps steps={steps} index={idx} progress={job.progress ?? 0} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-muted-foreground text-sm">
              可以離開這一頁，進度會保留；完成後會出現在「我的專案」。
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to="/projects">
                <FolderOpen />
                看我的專案
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (job.state === 'error') {
    const failedStep = job.failed_step != null ? job.steps?.[job.failed_step] : undefined
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2">
            <AlertCircle className="size-5" />
            扒譜失敗
          </CardTitle>
          <CardDescription className="truncate" title={project}>
            專案：{project}
            {failedStep ? `，卡在「${failedStep}」這一步` : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {job.error && <ErrorDetails message={job.error} />}
          <p className="text-muted-foreground text-sm">
            前面已經完成的步驟會沿用，重試不會從頭來過。
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void retry()} disabled={retrying}>
              {retrying ? <Loader2 className="animate-spin" /> : <RotateCcw />}
              {failedStep ? `從「${failedStep}」重試` : '重試'}
            </Button>
            {anotherButton('改扒別首')}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card role="status">
      <CardHeader>
        <CardTitle className="text-success flex items-center gap-2">
          <CheckCircle2 className="size-5" />
          扒譜完成
        </CardTitle>
        <CardDescription className="truncate" title={project}>
          專案「{project}」的 AI 譜已經準備好了。
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button asChild>
          <Link to="/editor" search={{ p: project }}>
            <FolderOpen />
            開啟編輯器
          </Link>
        </Button>
        {anotherButton('扒下一首')}
      </CardContent>
    </Card>
  )
}
