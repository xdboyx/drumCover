import { Fragment, memo } from 'react'
import { cn } from '@/lib/utils'
import type { Act, Bar } from '@/lib/types'
import { useEditor } from './context'
import { hasNote, isTripletBeat } from './lib/bar'
import { cellAct, cellUnsure } from './lib/confidence'
import { ROWS, TICKS, subLabel, subTitle, type RowDef } from './lib/constants'
import { useEditorStore } from './store'

const LABEL_COL = '7.5rem'

interface CellProps {
  row: RowDef
  bar: Bar
  act: Act
  index: number
  beat: number
  k: number
  triplet: boolean
  onToggle: (tick: number, inst: string) => void
}

/** 一個格子：有音顯示符號、底色深淺＝AI 信心、橘點＝值得用耳朵確認。用原生 title 當 tooltip（176 個格子掛 Radix 太重）。 */
const Cell = memo(function Cell({ row, bar, act, index, beat, k, triplet, onToggle }: CellProps) {
  const tick = beat * TICKS + k * (triplet ? 4 : 3)
  const on = hasNote(bar, tick, row.code)
  const a = cellAct(act, index, row.cls, beat, k, triplet)
  const unsure = cellUnsure(act, index, bar, row.code, tick, on)
  const title = `${row.name}｜第 ${beat + 1} 拍 ${subTitle(k, triplet)}｜AI 信心 ${(a * 100).toFixed(0)}%`
  return (
    <div
      title={title}
      aria-label={title}
      aria-pressed={on}
      role="button"
      onClick={() => onToggle(tick, row.code)}
      className={cn(
        'relative grid h-8 cursor-pointer place-items-center rounded-[5px] border text-[15px] font-bold',
        'hover:border-primary hover:ring-primary/30 hover:ring-2',
        on
          ? 'bg-background border-foreground/80 ring-foreground/80 ring-1'
          : k === 0
            ? 'bg-muted border-foreground/25'
            : 'bg-muted/40 border-border',
        k % 2 === 1 && !triplet && !on && 'border-dashed'
      )}
    >
      {!on && (
        <span
          className="bg-primary pointer-events-none absolute inset-0 rounded-[4px]"
          style={{ opacity: Math.min(0.55, a * 0.7) }}
        />
      )}
      <span className="relative">{on ? row.symbol : ''}</span>
      {unsure && <span className="bg-warning absolute top-[3px] right-[3px] size-[7px] rounded-full" />}
    </div>
  )
})

/**
 * 方格編輯：列＝樂器、每拍 4 格（16 分音符）或 3 格（三連音）。
 * 紅色播放頭與「目前拍」由 PlaybackEngine 直接改 DOM（[data-beat-marker]、[data-beat-head]、playhead ref）。
 */
export function NoteGrid() {
  const { actions, refs } = useEditor()
  const score = useEditorStore((s) => s.score)
  const act = useEditorStore((s) => s.act)
  const cur = useEditorStore((s) => s.cur)
  if (!score) return null
  const bar = score.bars[cur]
  const nb = bar.ticks / TICKS
  const beats = Array.from({ length: nb }, (_, j) => j)
  const tri = beats.map((j) => isTripletBeat(bar, j))

  return (
    <div
      ref={refs.grid}
      className="relative grid gap-x-2 gap-y-[3px] select-none"
      style={{ gridTemplateColumns: `${LABEL_COL} repeat(${nb}, minmax(0, 1fr))` }}
    >
      <div />
      {beats.map((j) => (
        <div
          key={j}
          data-beat-head
          className="group text-muted-foreground flex items-center justify-between px-0.5 text-xs"
        >
          <b className="text-foreground group-data-[current=true]:text-primary">第 {j + 1} 拍</b>
          <button
            type="button"
            title={tri[j] ? '切回 16 分音符' : '切換成三連音'}
            aria-pressed={tri[j]}
            onClick={() => actions.toggleTriplet(j)}
            className={cn(
              'h-5 min-w-6 rounded-[5px] border px-1.5 text-[11px] font-semibold',
              tri[j]
                ? 'bg-primary/15 border-primary text-primary'
                : 'text-muted-foreground hover:border-primary hover:text-primary'
            )}
          >
            3
          </button>
        </div>
      ))}

      <div />
      {beats.map((j) => (
        <div
          key={j}
          data-beat-marker
          className="grid gap-0.5"
          style={{ gridTemplateColumns: `repeat(${tri[j] ? 3 : 4}, 1fr)` }}
        >
          {Array.from({ length: tri[j] ? 3 : 4 }, (_, k) => (
            <div key={k} className="text-muted-foreground h-4 text-center text-[11px]">
              {subLabel(j, k, tri[j])}
            </div>
          ))}
        </div>
      ))}

      {ROWS.map((row) => (
        <Fragment key={row.code}>
          <div className="flex items-center justify-end gap-1.5 pr-2 text-[13px] whitespace-nowrap">
            {row.name}
            <i className="text-muted-foreground w-5 text-center text-[11px] not-italic">{row.symbol}</i>
          </div>
          {beats.map((j) => (
            <div
              key={j}
              className="grid gap-0.5"
              style={{ gridTemplateColumns: `repeat(${tri[j] ? 3 : 4}, 1fr)` }}
            >
              {Array.from({ length: tri[j] ? 3 : 4 }, (_, k) => (
                <Cell
                  key={k}
                  row={row}
                  bar={bar}
                  act={act}
                  index={cur}
                  beat={j}
                  k={k}
                  triplet={tri[j]}
                  onToggle={actions.toggleNote}
                />
              ))}
            </div>
          ))}
        </Fragment>
      ))}

      <div
        ref={refs.playhead}
        className="pointer-events-none absolute top-0 bottom-0 hidden w-0.5 bg-rose-600"
      />
    </div>
  )
}
