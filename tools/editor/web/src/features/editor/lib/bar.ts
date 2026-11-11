import type { Bar, ScoreEvent } from '@/lib/types'
import { EXCLUSIVE, TICKS } from './constants'

/**
 * 小節編輯的純函式：全部不可變，回傳新的 Bar，不修改傳入的物件。
 * 會改內容的操作（toggleNote、toggleTriplet、clearBar、applyBarContent）都標上 `edited: true`；
 * restoreBarContent 則是回到來源版本，會拿掉 `edited`。
 */

/** 小節內容：複製／貼上用，只含 tick、notes 與三連音拍 */
export interface BarContent {
  events: { tick: number; notes: string[] }[]
  triplets: number[]
}

const byTick = (a: { tick: number }, b: { tick: number }) => a.tick - b.tick

/** 第 j 拍（0 起算）是不是三連音：明確標記，或有不在 16 分格線上的音 */
export function isTripletBeat(b: Bar, j: number): boolean {
  return (
    (b.triplets ?? []).includes(j) ||
    b.events.some((e) => Math.floor(e.tick / TICKS) === j && e.tick % 3 !== 0)
  )
}

/** 某 tick 上有沒有某樂器 */
export function hasNote(b: Bar, tick: number, inst: string): boolean {
  const e = b.events.find((e) => e.tick === tick)
  return !!(e && e.notes.includes(inst))
}

/** 在 tick 加上或拿掉樂器；同位置 hi-hat 開/閉互斥（加一個會拿掉另一個）。 */
export function toggleNote(b: Bar, tick: number, inst: string): Bar {
  const events: ScoreEvent[] = b.events.map((e) => ({ ...e, notes: [...e.notes] }))
  let e = events.find((x) => x.tick === tick)
  if (!e) {
    e = { tick, notes: [] }
    events.push(e)
  }
  if (e.notes.includes(inst)) {
    e.notes = e.notes.filter((n) => n !== inst)
  } else {
    e.notes.push(inst)
    const excl = EXCLUSIVE[inst]
    if (excl) e.notes = e.notes.filter((n) => n !== excl)
  }
  return { ...b, events: events.filter((x) => x.notes.length).sort(byTick), edited: true }
}

/**
 * 第 j 拍在 16 分音符與三連音之間切換，並把原本的音就近對應：
 * 16 分 -> 三連：0->0、3->4、6->4、9->8（3 與 6 會合併到同一格）；
 * 三連 -> 16 分：0->0、4->3、8->9。
 */
export function toggleTriplet(b: Bar, j: number): Bar {
  const toTri = !isTripletBeat(b, j)
  const map: Record<number, number> = toTri ? { 0: 0, 3: 4, 6: 4, 9: 8 } : { 0: 0, 4: 3, 8: 9 }
  const merged = new Map<number, string[]>()
  for (const e of b.events) {
    const bj = Math.floor(e.tick / TICKS)
    const sub = e.tick % TICKS
    const t = bj === j ? j * TICKS + (map[sub] ?? sub) : e.tick
    merged.set(t, [...new Set([...(merged.get(t) ?? []), ...e.notes])])
  }
  const events = [...merged.entries()].map(([tick, notes]) => ({ tick, notes })).sort(byTick)
  const triplets = (b.triplets ?? []).filter((x) => x !== j)
  if (toTri) triplets.push(j)
  return { ...b, events, triplets, edited: true }
}

/** 擷取小節內容（複製、「同上一小節」用）。回傳的是深拷貝。 */
export function barContent(b: Bar): BarContent {
  return {
    events: b.events.map((e) => ({ tick: e.tick, notes: [...e.notes] })),
    triplets: [...(b.triplets ?? [])],
  }
}

/** 把內容貼到小節（取代原本的音）。 */
export function applyBarContent(b: Bar, c: BarContent): Bar {
  return {
    ...b,
    events: c.events.map((e) => ({ tick: e.tick, notes: [...e.notes] })),
    triplets: [...c.triplets],
    edited: true,
  }
}

/** 清空小節。 */
export function clearBar(b: Bar): Bar {
  return { ...b, events: [], triplets: [], edited: true }
}

/**
 * 「還原成來源版本」：用來源版本該小節的內容取代，並拿掉 edited 標記。
 * 舊資料的事件可能只有 slot（1 slot = 3 tick），這裡一併換算成 tick。
 */
export function restoreBarContent(
  b: Bar,
  source: { events: { tick?: number; slot?: number; notes: string[] }[]}
): Bar {
  const next: Bar = {
    ...b,
    events: source.events.map((e) => ({ tick: e.tick ?? (e.slot ?? 0) * 3, notes: [...e.notes] })),
    triplets: [],
  }
  delete next.edited
  return next
}

/** 某 tick 對應的影片秒數（依每拍起點線性內插；沒有 beats 就依小節頭尾均分）。 */
export function tickTime(b: Bar, tick: number): number {
  if (!b.beats) return b.t0 + ((b.t1 - b.t0) * tick) / b.ticks
  const j = Math.floor(tick / TICKS)
  const bt = b.beats
  return bt[j] + ((bt[j + 1] - bt[j]) * (tick % TICKS)) / TICKS
}

/** 影片時間 t 落在第幾小節（最後一個起點 ≤ t 的小節；容許 Chrome 把 currentTime 截斷的誤差） */
export function barIndexAt(bars: Bar[], t: number, eps = 0.005): number {
  let idx = 0
  for (let i = 0; i < bars.length; i++) if (bars[i].t0 <= t + eps) idx = i
  return idx
}
