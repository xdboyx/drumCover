import type { Bar } from '@/lib/types'

/**
 * 復原／重做堆疊（逐小節快照）。全部不可變：每個函式回傳新的 History。
 * Bar 本身不可變（見 bar.ts），所以快照直接存參照，不用深拷貝。
 */

export interface Snapshot {
  /** 小節索引（0 起算） */
  index: number
  bar: Bar
}

export interface History {
  undo: Snapshot[]
  redo: Snapshot[]
}

/** 復原堆疊最多保留的步數 */
export const MAX_HISTORY = 300

export const emptyHistory: History = { undo: [], redo: [] }

/** 修改某小節之前呼叫：把修改前的樣子推進復原堆疊，並清掉重做堆疊。超過上限就丟掉最舊的。 */
export function record(h: History, index: number, bar: Bar): History {
  const undo = [...h.undo, { index, bar }]
  if (undo.length > MAX_HISTORY) undo.splice(0, undo.length - MAX_HISTORY)
  return { undo, redo: [] }
}

export interface StepResult {
  history: History
  bars: Bar[]
  /** 被還原／重做的小節索引（呼叫端要跳到這裡） */
  index: number
}

function replaceAt(bars: Bar[], index: number, bar: Bar): Bar[] {
  const next = [...bars]
  next[index] = bar
  return next
}

/** 復原一步。沒有可復原的回傳 null。目前的樣子會進重做堆疊。 */
export function undoStep(h: History, bars: Bar[]): StepResult | null {
  const snap = h.undo[h.undo.length - 1]
  if (!snap) return null
  return {
    history: {
      undo: h.undo.slice(0, -1),
      redo: [...h.redo, { index: snap.index, bar: bars[snap.index] }],
    },
    bars: replaceAt(bars, snap.index, snap.bar),
    index: snap.index,
  }
}

/** 重做一步。沒有可重做的回傳 null。目前的樣子會回到復原堆疊。 */
export function redoStep(h: History, bars: Bar[]): StepResult | null {
  const snap = h.redo[h.redo.length - 1]
  if (!snap) return null
  return {
    history: {
      undo: [...h.undo, { index: snap.index, bar: bars[snap.index] }],
      redo: h.redo.slice(0, -1),
    },
    bars: replaceAt(bars, snap.index, snap.bar),
    index: snap.index,
  }
}
