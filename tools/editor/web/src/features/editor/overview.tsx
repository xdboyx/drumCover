import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { barUnsureCached } from './lib/confidence'
import { useEditor } from './context'
import { useEditorStore } from './store'

const LEGEND = [
  { label: 'AI 有點不確定', cls: 'bg-warning/25' },
  { label: 'AI 很不確定（優先檢查）', cls: 'bg-warning/70' },
  { label: '你改過的小節', cls: 'border-success border-2 bg-card' },
  { label: '整小節休止', cls: 'bg-muted-foreground/25' },
]

/** 小節總覽：每個小節一個小方塊，每 4 個一組（對應譜面一行），點一下跳到該小節。 */
export const Overview = memo(function Overview() {
  const { playback } = useEditor()
  const bars = useEditorStore((s) => s.score?.bars)
  const act = useEditorStore((s) => s.act)
  const cur = useEditorStore((s) => s.cur)
  if (!bars) return null
  return (
    <Card className="gap-2 py-3">
      <CardContent className="space-y-2 px-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="text-muted-foreground text-xs font-semibold">小節總覽（點一下跳到該小節）</h2>
          <ul className="text-muted-foreground flex flex-wrap gap-x-3 gap-y-0.5 text-[11px]">
            {LEGEND.map((l) => (
              <li key={l.label} className="flex items-center gap-1">
                <span className={cn('border-border inline-block h-2.5 w-3 rounded-[3px] border', l.cls)} />
                {l.label}
              </li>
            ))}
            <li className="flex items-center gap-1">
              <span className="outline-primary inline-block h-2.5 w-3 rounded-[3px] outline-2" />
              目前小節
            </li>
          </ul>
        </div>
        <div className="flex flex-wrap gap-y-1">
          {bars.map((b, i) => {
            const u = barUnsureCached(act, i, b)
            const rest = b.events.length === 0
            const title =
              `第 ${i + 1} 小節` + (u ? `：${u} 處不確定` : '') + (b.edited ? '（已修改）' : '')
            return (
              <button
                key={i}
                type="button"
                title={title}
                aria-label={title}
                aria-current={i === cur ? 'true' : undefined}
                onClick={() => playback.go(i)}
                className={cn(
                  'text-muted-foreground mr-[3px] grid h-[22px] min-w-[30px] place-items-center rounded-[4px] border text-[10px] tabular-nums',
                  i % 4 === 0 && i > 0 && 'ml-2',
                  'bg-card hover:border-primary',
                  rest && 'bg-muted-foreground/25',
                  u >= 3 ? 'bg-warning/70 text-foreground' : u >= 1 && 'bg-warning/25',
                  b.edited && 'border-success border-2',
                  i === cur && 'outline-primary text-foreground font-bold outline-2 outline-offset-1'
                )}
              >
                {i + 1}
              </button>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
})
