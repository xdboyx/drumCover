import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { AlertCircle, AudioLines, FolderOpen, Plus, Search, SearchX, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { useJob, useRefreshJob } from '@/hooks/use-job'
import * as api from '@/lib/api'
import { filterAndSort, type SortKey } from './lib/filter-sort'
import { ProjectRow } from './project-row'
import { useProjectList } from './use-project-list'

const SORT_LABEL: Record<SortKey, string> = { updated: '最近更新', name: '名稱' }

function ListSkeleton() {
  return (
    <ul className="divide-y" aria-busy="true" aria-label="載入專案中">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex items-center gap-3 px-4 py-3">
          <Skeleton className="size-9 rounded-md" />
          <div className="grid flex-1 gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </li>
      ))}
    </ul>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <div className="bg-muted text-muted-foreground flex size-12 items-center justify-center rounded-full">
        <FolderOpen className="size-6" />
      </div>
      <div className="grid gap-1">
        <p className="font-medium">還沒有專案</p>
        <p className="text-muted-foreground text-sm">
          貼上 YouTube 網址或本機 mp4，扒完的鼓譜就會出現在這裡。
        </p>
      </div>
      <Button asChild>
        <Link to="/">
          <AudioLines />
          去扒譜
        </Link>
      </Button>
    </div>
  )
}

export function ProjectsPage() {
  const { job, busy } = useJob()
  const refresh = useRefreshJob()
  const { data, isLoading, error, refetch } = useProjectList()
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<SortKey>('updated')

  async function retry(name: string) {
    try {
      await api.projectRetry(name)
    } catch (e) {
      toast.error((e as Error).message)
    }
    refresh()
  }

  const total = data?.length ?? 0
  const shown = data ? filterAndSort(data, query, sort) : []

  return (
    <>
      <Header title="我的專案" />
      <Main width="list" className="grid content-start gap-4">
        {total > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-48 flex-1">
              <Search
                aria-hidden
                className="text-muted-foreground pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2"
              />
              <Input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
                placeholder="搜尋專案名稱"
                aria-label="搜尋專案名稱"
                className="ps-9! pe-9! [&::-webkit-search-cancel-button]:hidden"
                autoComplete="off"
              />
              {query && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute end-0.5 top-1/2 size-8 -translate-y-1/2"
                  onClick={() => setQuery('')}
                  aria-label="清除搜尋"
                >
                  <X />
                </Button>
              )}
            </div>
            <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
              <SelectTrigger className="w-44" aria-label="排序方式">
                <span className="text-muted-foreground">排序：</span>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
                  <SelectItem key={k} value={k}>
                    {SORT_LABEL[k]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button asChild variant="outline">
              <Link to="/">
                <Plus />
                新增扒譜
              </Link>
            </Button>
          </div>
        )}

        {total > 0 && (
          <p className="text-muted-foreground -mb-2 text-xs" aria-live="polite">
            {query.trim() ? `找到 ${shown.length} / ${total} 個專案` : `共 ${total} 個專案`}
          </p>
        )}

        <Card className="gap-0 overflow-hidden py-0">
          {isLoading ? (
            <ListSkeleton />
          ) : error ? (
            <div role="alert" className="flex flex-col items-center gap-3 px-6 py-12 text-center">
              <AlertCircle className="text-destructive size-6" />
              <div className="grid gap-1">
                <p className="font-medium">專案清單載入失敗</p>
                <p className="text-muted-foreground text-sm">{(error as Error).message}</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => void refetch()}>
                重新載入
              </Button>
            </div>
          ) : total === 0 ? (
            <EmptyState />
          ) : shown.length === 0 ? (
            <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
              <SearchX className="text-muted-foreground size-6" />
              <p className="text-sm">找不到名稱含「{query.trim()}」的專案</p>
              <Button variant="ghost" size="sm" onClick={() => setQuery('')}>
                清除搜尋
              </Button>
            </div>
          ) : (
            <ul className="divide-y">
              {shown.map((p) => (
                <ProjectRow key={p.name} p={p} job={job} busy={busy} onRetry={retry} />
              ))}
            </ul>
          )}
        </Card>
      </Main>
    </>
  )
}
