import { ChevronLeft, ChevronRight, ClipboardPaste, Copy, CopyPlus, Eraser, History } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useEditor } from './context'
import { formatTime } from './lib/playhead'
import { useEditorStore } from './store'

/** 小節工具列：上一／下一小節、目前小節資訊、同上一小節、複製、貼上、清空、還原成來源版本。 */
export function BarToolbar() {
  const { actions, playback, readOnly } = useEditor()
  const bars = useEditorStore((s) => s.score?.bars)
  const cur = useEditorStore((s) => s.cur)
  const hasClip = useEditorStore((s) => s.clip !== null)
  if (!bars) return null
  const bar = bars[cur]

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon-sm"
          title="上一小節 (←)"
          aria-label="上一小節"
          disabled={cur === 0}
          onClick={() => playback.go(cur - 1)}
        >
          <ChevronLeft />
        </Button>
        <div className="min-w-32 text-center leading-tight">
          <div className="text-lg font-bold tabular-nums">第 {cur + 1} 小節</div>
          <div className="text-muted-foreground text-[11px] tabular-nums">
            共 {bars.length} 小節・{formatTime(bar.t0)} – {formatTime(bar.t1)}
          </div>
        </div>
        <Button
          variant="outline"
          size="icon-sm"
          title="下一小節 (→)"
          aria-label="下一小節"
          disabled={cur === bars.length - 1}
          onClick={() => playback.go(cur + 1)}
        >
          <ChevronRight />
        </Button>
        {bar.edited && (
          <Badge variant="outline" className="border-success text-success ml-1">
            已修改
          </Badge>
        )}
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          title="把上一小節的內容複製到這一小節"
          disabled={cur === 0}
          onClick={actions.copyPrev}
        >
          <CopyPlus /> 同上一小節
        </Button>
        <Button variant="outline" size="sm" title="複製這一小節 (Ctrl+C)" onClick={actions.copy}>
          <Copy /> 複製
        </Button>
        <Button
          variant="outline"
          size="sm"
          title="貼上已複製的小節 (Ctrl+V)"
          disabled={!hasClip}
          onClick={actions.paste}
        >
          <ClipboardPaste /> 貼上
        </Button>
        <Button variant="outline" size="sm" title="清空這一小節" onClick={actions.clear}>
          <Eraser /> 清空
        </Button>
        <Button
          variant="outline"
          size="sm"
          title="回到來源版本的內容（來源已刪除則回到 AI 譜）"
          onClick={actions.revert}
        >
          <History /> 還原成來源版本
        </Button>
      </div>
      {readOnly && (
        <p className="text-warning basis-full text-xs">
          唯讀：這份是 AI 譜（或舊 AI 譜）。修改時會先請你命名一個新的編輯版本。
        </p>
      )}
    </div>
  )
}
