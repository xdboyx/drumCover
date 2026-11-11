import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'
import { versionsKey } from './use-editor-actions'
import { useEditorStore } from './store'

export type DataStatus = 'no-project' | 'loading' | 'error' | 'ready'

/**
 * 依網址的 p / v 載入鼓譜到 store，並用 TanStack Query 管版本清單。
 *
 * - 網址對上已載入的專案與版本就不重抓（建立版本後我們先載入再改網址，避免蓋掉剛套用的修改）。
 * - 離開頁面時清空 store，下次進來一定重新載入。
 * - 版本清單不存在或鼓譜載不到時回傳 error 與伺服器訊息，由頁面顯示友善說明。
 */
export function useEditorData(project: string | undefined, version: string) {
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null)
  const loaded = useEditorStore((s) => s.loaded)

  useEffect(() => {
    if (!project) return
    const cur = useEditorStore.getState().loaded
    if (cur?.project === project && cur.version === version) return
    let cancelled = false
    api
      .getScore(project, version)
      .then((d) => {
        if (cancelled) return
        setFailure(null)
        useEditorStore.getState().load({
          project,
          version,
          score: d.score,
          act: d.act,
          media: d.media,
        })
      })
      .catch((e: Error) => {
        if (!cancelled) setFailure({ key: `${project}/${version}`, message: e.message })
      })
    return () => {
      cancelled = true
    }
  }, [project, version])

  useEffect(() => () => useEditorStore.getState().reset(), [])

  const versionsQuery = useQuery({
    queryKey: versionsKey(project ?? ''),
    queryFn: () => api.getVersions(project!),
    enabled: !!project,
  })

  const projectReady = !!project && loaded?.project === project
  const failed = failure?.key === `${project}/${version}` ? failure.message : null
  let status: DataStatus
  if (!project) status = 'no-project'
  else if (failed) status = 'error'
  else if (projectReady && versionsQuery.data) status = 'ready'
  else if (versionsQuery.isError && !projectReady) status = 'error'
  else status = 'loading'

  const error =
    failed ?? (versionsQuery.error instanceof Error ? versionsQuery.error.message : null)
  return { status, error, versions: versionsQuery.data ?? [], loaded }
}
