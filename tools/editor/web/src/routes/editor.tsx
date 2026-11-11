import { createFileRoute } from '@tanstack/react-router'
import { EditorPage } from '@/features/editor'

export interface EditorSearch {
  /** 專案名稱 */
  p?: string
  /** 版本 id，省略代表 "ai" */
  v?: string
}

export const Route = createFileRoute('/editor')({
  validateSearch: (search: Record<string, unknown>): EditorSearch => ({
    p: typeof search.p === 'string' && search.p ? search.p : undefined,
    v: typeof search.v === 'string' && search.v ? search.v : undefined,
  }),
  component: EditorRoute,
})

function EditorRoute() {
  const { p, v } = Route.useSearch()
  return <EditorPage project={p} version={v ?? 'ai'} />
}
