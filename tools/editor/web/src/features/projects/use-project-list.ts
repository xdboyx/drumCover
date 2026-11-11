import { useQuery } from '@tanstack/react-query'
import { JOB_POLL_IDLE_MS, JOB_POLL_RUNNING_MS, useJob } from '@/hooks/use-job'
import * as api from '@/lib/api'

/** 專案清單（GET /api/project_list）。有工作在跑時每秒更新，否則約 4 秒。 */
export function useProjectList() {
  const { busy } = useJob()
  return useQuery({
    queryKey: ['project_list'],
    queryFn: api.projectList,
    refetchInterval: busy ? JOB_POLL_RUNNING_MS : JOB_POLL_IDLE_MS,
  })
}
