import type { JobStatus } from '@/lib/types'

/** 整個工作的進度 0~1：已完成的步驟數加上目前步驟的進度，除以總步驟數。 */
export function overallProgress(job: Pick<JobStatus, 'steps' | 'step_index' | 'progress'>): number {
  const total = job.steps?.length ?? 0
  if (total === 0) return job.progress ?? 0
  const done = Math.min(job.step_index ?? 0, total)
  const cur = Math.min(Math.max(job.progress ?? 0, 0), 1)
  return Math.min((done + cur) / total, 1)
}
