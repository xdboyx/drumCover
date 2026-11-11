import type { Act, Bar } from '@/lib/types'
import { CLASS_OF, ROWS, TICKS, UNSURE_CLASSES } from './constants'
import { hasNote, isTripletBeat } from './bar'

/**
 * AI 信心與「不確定」標記。規則與舊版 index.html 完全相同。
 * act[i][類別] = { s16: 每個 16 分格的擊打機率, t3: 每個三連音格的擊打機率 }。
 */

/** 第 i 小節、某類別、第 j 拍第 k 格的 AI 擊打機率（0~1）。沒有資料回傳 0。 */
export function cellAct(
  act: Act,
  i: number,
  cls: string | null,
  j: number,
  k: number,
  triplet: boolean
): number {
  if (!act || !cls || !act[i]) return 0
  const a = act[i][cls]
  if (!a) return 0
  return (triplet ? a.t3[j * 3 + k] : a.s16[j * 4 + k]) ?? 0
}

/**
 * 這一格值不值得用耳朵確認。
 * on（有寫音）：AI 機率 < 0.3 算不確定；
 * 沒寫音：AI 機率 >= 0.2 算不確定，但同類別其他樂器已寫在這格就不算。
 */
export function cellUnsure(
  act: Act,
  i: number,
  bar: Bar,
  inst: string,
  tick: number,
  on: boolean
): boolean {
  const cls = CLASS_OF[inst]
  if (!cls || !act) return false
  const j = Math.floor(tick / TICKS)
  const sub = tick % TICKS
  const tri = isTripletBeat(bar, j)
  const a = tri ? cellAct(act, i, cls, j, sub / 4, true) : cellAct(act, i, cls, j, sub / 3, false)
  if (on) return a < 0.3
  const sibling = ROWS.some((r) => r.cls === cls && hasNote(bar, tick, r.code))
  return !sibling && a >= 0.2
}

/** 第 i 小節有幾處不確定（小節總覽的顏色依此決定：>=1 淺橘、>=3 深橘）。 */
export function barUnsure(act: Act, i: number, bar: Bar): number {
  if (!bar.events.length && !act) return 0
  let n = 0
  const nb = bar.ticks / TICKS
  for (const cls of UNSURE_CLASSES) {
    const insts = ROWS.filter((r) => r.cls === cls).map((r) => r.code)
    for (let j = 0; j < nb; j++) {
      const tri = isTripletBeat(bar, j)
      for (let k = 0; k < (tri ? 3 : 4); k++) {
        const tick = j * TICKS + k * (tri ? 4 : 3)
        const written = insts.find((x) => hasNote(bar, tick, x))
        if (cellUnsure(act, i, bar, written ?? insts[0], tick, written !== undefined)) n++
      }
    }
  }
  return n
}

const unsureCaches = new WeakMap<object, WeakMap<Bar, number>>()
const NO_ACT = {}

/**
 * barUnsure 的快取版：Bar 不可變，同一個 Bar 物件、同一份 act 的結果不會變，
 * 所以改一個小節時，總覽只需要重算那一個小節。
 */
export function barUnsureCached(act: Act, i: number, bar: Bar): number {
  const key: object = act ?? NO_ACT
  let perBar = unsureCaches.get(key)
  if (!perBar) {
    perBar = new WeakMap()
    unsureCaches.set(key, perBar)
  }
  let n = perBar.get(bar)
  if (n === undefined) {
    n = barUnsure(act, i, bar)
    perBar.set(bar, n)
  }
  return n
}
