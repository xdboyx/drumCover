import { useEffect } from 'react'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { useJob } from '@/hooks/use-job'
import { HowItWorks } from './how-it-works'
import { ImportForm } from './import-form'
import { ImportJobCard } from './import-job-card'
import { RecentProjects } from './recent-projects'
import { resultKey, useImportUi } from './store'

/** 首頁「扒譜」：單一任務——貼來源、開始扒譜；進行中在同一個位置顯示進度。 */
export function ImportPage() {
  const { job } = useJob()
  const { dismissed, reset } = useImportUi()
  const running = job?.state === 'running'

  // 新的工作開始後，之前收起來的結果不再算數
  useEffect(() => {
    if (running) reset()
  }, [running, reset])

  const showJob =
    !!job &&
    job.kind === 'import' &&
    job.state !== 'idle' &&
    (running || dismissed !== resultKey(job.project, job.state))

  return (
    <>
      <Header title="扒譜" />
      <Main width="form" className="grid content-start gap-8">
        {showJob ? <ImportJobCard job={job} /> : <ImportForm />}
        <HowItWorks />
        <RecentProjects />
      </Main>
    </>
  )
}
