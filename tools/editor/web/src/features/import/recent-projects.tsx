import { Link } from '@tanstack/react-router'
import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { filterAndSort } from '@/features/projects/lib/filter-sort'
import { ProjectRow } from '@/features/projects/project-row'
import { useProjectList } from '@/features/projects/use-project-list'

const RECENT_COUNT = 5

/** 首頁下方：最近更新的 5 個專案（只列扒完、可以開編輯器的），整列可點；完整清單在「我的專案」。 */
export function RecentProjects() {
  const { data, isLoading } = useProjectList()
  const ready = (data ?? []).filter((p) => p.status === 'ready')
  const recent = filterAndSort(ready, '', 'updated').slice(0, RECENT_COUNT)

  if (isLoading) {
    return (
      <section aria-label="最近的專案" className="grid gap-3">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-16 w-full rounded-xl" />
      </section>
    )
  }
  if (recent.length === 0) return null

  return (
    <section aria-labelledby="recent-title" className="grid gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="recent-title" className="text-sm font-semibold">
          最近的專案
        </h2>
        {ready.length > RECENT_COUNT && (
          <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
            <Link to="/projects">
              查看全部（{ready.length}）
              <ArrowRight />
            </Link>
          </Button>
        )}
      </div>
      <Card className="gap-0 overflow-hidden py-0">
        <ul className="divide-y">
          {recent.map((p) => (
            <ProjectRow key={p.name} p={p} busy={false} compact />
          ))}
        </ul>
      </Card>
      {ready.length <= RECENT_COUNT && (
        <Button asChild variant="ghost" size="sm" className="text-muted-foreground justify-self-start">
          <Link to="/projects">
            到「我的專案」管理
            <ArrowRight />
          </Link>
        </Button>
      )}
    </section>
  )
}
