import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '@/lib/api'
import type { JobKind, JobStatus } from '@/lib/types'

export const JOB_KEY = ['job'] as const
export const JOB_POLL_RUNNING_MS = 1000
export const JOB_POLL_IDLE_MS = 4000

/**
 * 全站共用的長時間工作狀態（GET /api/job）。
 * running 時每 1 秒輪詢，否則約 4 秒。所有呼叫端共用同一個 query，不會重複請求。
 */
export function useJob() {
  const query = useQuery({
    queryKey: JOB_KEY,
    queryFn: api.job,
    refetchInterval: (q) =>
      q.state.data?.state === 'running' ? JOB_POLL_RUNNING_MS : JOB_POLL_IDLE_MS,
    refetchIntervalInBackground: false,
  })
  const job: JobStatus | undefined = query.data
  return { job, busy: job?.state === 'running', isLoading: query.isLoading, error: query.error }
}

/** 送出工作（扒譜、輸出…）後呼叫，立刻重抓工作狀態與專案清單，不用等下一次輪詢。 */
export function useRefreshJob() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: JOB_KEY })
    void qc.invalidateQueries({ queryKey: ['project_list'] })
  }
}

/**
 * 某種工作從 running 變成 done 時呼叫 callback（例如重新扒譜完成後重新載入鼓譜）。
 * callback 不必 memoize。
 */
export function useOnJobFinished(
  kind: JobKind,
  callback: (job: JobStatus) => void,
  project?: string
) {
  const { job } = useJob()
  const prev = useRef<JobStatus | undefined>(undefined)
  const cb = useRef(callback)
  useEffect(() => {
    cb.current = callback
  })
  useEffect(() => {
    const p = prev.current
    prev.current = job
    if (
      p?.state === 'running' &&
      job &&
      job.state !== 'running' &&
      job.kind === kind &&
      (project === undefined || job.project === project)
    ) {
      cb.current(job)
    }
  }, [job, kind, project])
}

export const JOB_KIND_LABEL: Record<JobKind, { running: string; failed: string }> = {
  import: { running: '扒譜中', failed: '扒譜失敗' },
  reimport: { running: '重新扒譜中', failed: '重新扒譜失敗' },
  render: { running: '輸出中', failed: '輸出失敗' },
}
