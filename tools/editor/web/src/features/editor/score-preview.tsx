import { useRef } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { useEditor } from './context'
import { useScorePreview } from './use-score-preview'

/**
 * 即時譜面預覽：顯示影片目前時間所在那一行的鼓譜（與練習影片同一套排版）與藍色游標。
 * 譜面圖一律白底（暗色主題下也是），游標用 multiply 混色疊在上面。
 */
export function ScorePreview() {
  const { refs, playback } = useEditor()
  const imgRef = useRef<HTMLImageElement>(null)
  const cursorRef = useRef<HTMLDivElement>(null)
  const { ready, barAt } = useScorePreview({ video: refs.video, img: imgRef, cursor: cursorRef })

  return (
    <div className="relative min-h-16 overflow-hidden rounded-md border bg-white">
      {!ready && <Skeleton className="absolute inset-0 rounded-none bg-neutral-200" />}
      <img
        ref={imgRef}
        alt="譜面預覽"
        title="點譜面上的小節可直接跳過去"
        className="block w-full cursor-pointer bg-white"
        style={{ visibility: ready ? 'visible' : 'hidden' }}
        onClick={(e) => {
          const bar = barAt(e.clientX)
          if (bar !== null) playback.go(bar)
        }}
      />
      <div
        ref={cursorRef}
        className="pointer-events-none absolute hidden"
        style={{ background: 'rgb(110,185,255)', mixBlendMode: 'multiply' }}
      />
    </div>
  )
}
