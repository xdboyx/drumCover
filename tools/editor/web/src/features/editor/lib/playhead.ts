import type { Bar } from '@/lib/types'
import { TICKS } from './constants'

/** 小節每拍的起點秒數（拍數 + 1 個）。舊資料沒有 beats 時依小節頭尾均分。 */
export function barBeats(b: Bar): number[] {
  if (b.beats && b.beats.length >= 2) return b.beats
  const n = Math.max(1, Math.round(b.ticks / TICKS))
  return Array.from({ length: n + 1 }, (_, j) => b.t0 + ((b.t1 - b.t0) * j) / n)
}

export interface PlayheadPosition {
  /** 第幾拍（0 起算） */
  beat: number
  /** 在該拍內的位置 0~1 */
  frac: number
}

/** 播放時間 t 在小節內的位置（依實際拍點分段）。不在小節內回傳 null。 */
export function playheadPosition(b: Bar, t: number): PlayheadPosition | null {
  if (!(t >= b.t0 && t <= b.t1)) return null
  const bt = barBeats(b)
  let j = 0
  while (j < bt.length - 2 && t >= bt[j + 1]) j++
  const span = bt[j + 1] - bt[j]
  const frac = span > 0 ? Math.min(1, Math.max(0, (t - bt[j]) / span)) : 0
  return { beat: j, frac }
}

/**
 * 播放這一小節時從哪個媒體時間開始：提前一拍，或只提前 0.05 秒。
 * 不會小於 0。
 */
export function barStartTime(b: Bar, preroll: boolean): number {
  const beat = b.beats && b.beats.length >= 2 ? b.beats[1] - b.beats[0] : (b.t1 - b.t0) / 4
  return Math.max(0, b.t0 - (preroll ? beat : 0.05))
}

/** 秒數顯示成 m:ss.ss */
export function formatTime(t: number): string {
  return `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`
}
