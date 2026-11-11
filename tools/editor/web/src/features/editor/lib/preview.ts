import type { PreviewLine } from '@/lib/types'

/**
 * 影片時間比對的容許誤差（秒）。
 *
 * 點某一小節時程式把 video.currentTime 設成該小節的 t0，但 Chrome 讀回來的 currentTime
 * 會被截到微秒精度（設 9.161234567 讀回 9.161234），略小於該小節第一個音的時間（== t0）。
 * 嚴格比對會選到上一個音／上一行，所以所有「時間是否已到」的比較都要加這個容許誤差。
 */
export const TIME_EPS = 0.005

/** 游標行首條件：比行起點早不到 0.01 秒仍視為已進入該行（沿用舊版） */
const LINE_LEAD = 0.01

/** 現在時間 t 該顯示哪一行（lines 是每行的 [起, 止] 秒）。lines 為空回傳 0。 */
export function lineIndexAt(lines: readonly [number, number][], t: number): number {
  let li = 0
  for (let i = 0; i < lines.length; i++) if (t + TIME_EPS >= lines[i][0]) li = i
  return li
}

/**
 * 游標該在哪個音符的 x（像素，圖片座標）：最近一個「已到達」的音。
 * 還沒進入這一行（t 遠早於行首）或這一行還沒有音到達時回傳 null。
 */
export function cursorX(line: Pick<PreviewLine, 't0' | 'evs'>, t: number): number | null {
  if (t < line.t0 - LINE_LEAD) return null
  let x: number | null = null
  for (const [et, ex] of line.evs) {
    if (et <= t + TIME_EPS) x = ex
    else break
  }
  return x
}

/**
 * 暫停時的游標 x：游標要落在「t 所在的小節」。
 *
 * 播放中用 cursorX（最近一個已到達的音）；但暫停在某小節起點時，若該小節第一個音不在第一拍，
 * cursorX 會停在上一小節最後一個音（或整份譜第一小節完全沒有游標）。
 * 這裡改成：cursorX 落在 t 所在小節的 x 範圍內就用它，否則用該小節內時間最早的音；
 * 該小節沒有任何音（休止、% 記號、多小節休止）時維持 cursorX 的結果。
 */
export function restingCursorX(
  line: Pick<PreviewLine, 't0' | 't1' | 'evs' | 'measures'>,
  t: number
): number | null {
  const base = cursorX(line, t)
  const ms = line.measures
  let mi = -1
  for (let i = 0; i < ms.length; i++) if (t + TIME_EPS >= ms[i].t0) mi = i
  if (mi < 0) return base
  const { x0 } = ms[mi]
  // 小節的右邊界：下一個小節的 x0（沒有下一個就是 x1）
  const x1 = mi + 1 < ms.length ? ms[mi + 1].x0 : ms[mi].x1
  if (base !== null && base >= x0 && base < x1) return base
  let first: number | null = null
  for (const [, ex] of line.evs) {
    if (ex >= x0 && ex < x1) {
      first = ex
      break
    }
  }
  return first ?? base
}
