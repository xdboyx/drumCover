import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { toast } from 'sonner'
import * as api from '@/lib/api'
import type { PreviewLine } from '@/lib/types'
import { useEditorPrefs } from '@/stores/editor-prefs-store'
import { cursorX, lineIndexAt, restingCursorX } from './lib/preview'
import { useEditorStore } from './store'

/** 更新頻率（毫秒）。不用 rAF：分頁在背景或被遮住時 rAF 會停 */
const FRAME_MS = 30
/** 預覽請求失敗後，隔多久才重試（毫秒），避免每 30 毫秒打一次伺服器 */
const RETRY_MS = 3000

interface PreviewState {
  /** 版次：鼓譜內容或選項一變就加一，擋掉過期的回應 */
  ver: number
  cache: Map<number, PreviewLine>
  lines: [number, number][] | null
  shown: PreviewLine | null
  loading: boolean
  prefetching: boolean
  failedAt: number
  failedVer: number
}

interface Refs {
  video: RefObject<HTMLVideoElement | null>
  img: RefObject<HTMLImageElement | null>
  cursor: RefObject<HTMLDivElement | null>
}

/**
 * 即時譜面預覽：用目前記憶體中的鼓譜（含未存修改）向伺服器排版，
 * 顯示「影片目前時間」所在那一行的 PNG 與藍色游標。
 *
 * - 每一行的結果會快取；鼓譜一改（store.rev）整個作廢。
 * - 用 setInterval 每 30 毫秒更新；圖片與游標位置直接改 DOM，不走 setState。
 * - 判斷哪一行、游標在哪個音，一律經過 lineIndexAt / cursorX / restingCursorX（內含影片 currentTime 的容許誤差）。
 */
export function useScorePreview({ video, img, cursor }: Refs) {
  const rev = useEditorStore((s) => s.rev)
  const simile = useEditorPrefs((s) => s.simile)
  const [ready, setReady] = useState(false)
  const st = useRef<PreviewState>({
    ver: 0,
    cache: new Map(),
    lines: null,
    shown: null,
    loading: false,
    prefetching: false,
    failedAt: 0,
    failedVer: -1,
  })

  // 鼓譜或選項改了：作廢所有快取（舊圖先留著，新圖到了再換，避免閃爍）
  useEffect(() => {
    const s = st.current
    s.ver++
    s.cache.clear()
    s.lines = null
  }, [rev, simile])

  useEffect(() => {
    const s = st.current

    async function fetchLine(li: number) {
      const ver = s.ver
      const score = useEditorStore.getState().score
      if (!score) return
      const d = await api.previewLine({ score, line: li, simile: useEditorPrefs.getState().simile })
      if (ver === s.ver) {
        s.cache.set(li, d)
        s.lines = d.lines
      }
    }

    function frame() {
      const { score, cur } = useEditorStore.getState()
      const imgEl = img.current
      const cursorEl = cursor.current
      if (!score || !imgEl || !cursorEl) return
      const v = video.current
      const t = v && v.getAttribute('src') && v.readyState > 0 ? v.currentTime : score.bars[cur].t0
      const li = s.lines ? lineIndexAt(s.lines, t) : 0
      const d = s.cache.get(li)
      if (!d) {
        const recentlyFailed = s.failedVer === s.ver && Date.now() - s.failedAt < RETRY_MS
        if (!s.loading && !recentlyFailed) {
          s.loading = true
          const ver = s.ver
          fetchLine(li)
            .catch((e: Error) => {
              s.failedVer = ver
              s.failedAt = Date.now()
              toast.error(`譜面預覽失敗：${e.message}`, { id: 'preview-error' })
            })
            .finally(() => {
              s.loading = false
            })
        }
        return
      }
      if (s.shown !== d) {
        imgEl.src = `data:image/png;base64,${d.png}`
        s.shown = d
        setReady(true)
      }
      // 播放中游標跟著最近到達的音；暫停時落在所在小節（用實際 video.paused，原生控制列播放也算播放中）
      const playing = !!v && !v.paused
      const x = playing ? cursorX(d, t) : restingCursorX(d, t)
      if (x === null) {
        cursorEl.style.display = 'none'
      } else {
        const k = d.cursor
        cursorEl.style.display = 'block'
        cursorEl.style.left = `${((x - k.dx) / d.width) * 100}%`
        cursorEl.style.width = `${(k.w / d.width) * 100}%`
        cursorEl.style.top = `${(k.y0 / d.height) * 100}%`
        cursorEl.style.height = `${((k.y1 - k.y0) / d.height) * 100}%`
      }
      // 預先排好下一行
      if (!s.loading && !s.prefetching && s.lines && li + 1 < s.lines.length && !s.cache.has(li + 1)) {
        s.prefetching = true
        fetchLine(li + 1)
          .catch(() => {})
          .finally(() => {
            s.prefetching = false
          })
      }
    }

    const id = setInterval(frame, FRAME_MS)
    return () => clearInterval(id)
  }, [video, img, cursor])

  /** 點譜面上的小節：回傳該小節編號（0 起算），點在小節外回傳 null */
  const barAt = useCallback(
    (clientX: number): number | null => {
      const d = st.current.shown
      const el = img.current
      if (!d || !el) return null
      const r = el.getBoundingClientRect()
      const x = ((clientX - r.left) / r.width) * d.width
      return d.measures.find((m) => x >= m.x0 && x < m.x1)?.bar ?? null
    },
    [img]
  )

  return { ready, barAt }
}
