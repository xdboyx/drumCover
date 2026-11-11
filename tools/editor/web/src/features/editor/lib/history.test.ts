import { describe, expect, it } from 'vitest'
import type { Bar } from '@/lib/types'
import { MAX_HISTORY, emptyHistory, record, redoStep, undoStep } from './history'

const bar = (n: number): Bar => ({ t0: n, t1: n + 1, ticks: 48, events: [] })

describe('history', () => {
  it('沒有紀錄時復原／重做回傳 null', () => {
    expect(undoStep(emptyHistory, [bar(0)])).toBeNull()
    expect(redoStep(emptyHistory, [bar(0)])).toBeNull()
  })

  it('復原會還原該小節、回報小節索引，並把目前樣子放進重做', () => {
    const before = bar(1)
    const after = { ...before, edited: true }
    const h = record(emptyHistory, 1, before)
    const r = undoStep(h, [bar(0), after])!
    expect(r.index).toBe(1)
    expect(r.bars[1]).toBe(before)
    expect(r.history.undo).toHaveLength(0)
    expect(r.history.redo).toHaveLength(1)
    const again = redoStep(r.history, r.bars)!
    expect(again.bars[1]).toBe(after)
    expect(again.history.undo).toHaveLength(1)
    expect(again.history.redo).toHaveLength(0)
  })

  it('不會修改傳入的 bars 陣列', () => {
    const bars = [bar(0), { ...bar(1), edited: true }]
    const h = record(emptyHistory, 1, bar(1))
    undoStep(h, bars)
    expect(bars[1].edited).toBe(true)
  })

  it('新的修改會清掉重做堆疊', () => {
    let h = record(emptyHistory, 0, bar(0))
    const r = undoStep(h, [{ ...bar(0), edited: true }])!
    expect(r.history.redo).toHaveLength(1)
    h = record(r.history, 0, bar(0))
    expect(h.redo).toHaveLength(0)
  })

  it('最多保留 MAX_HISTORY 步，丟掉最舊的', () => {
    let h = emptyHistory
    for (let i = 0; i < MAX_HISTORY + 5; i++) h = record(h, i, bar(i))
    expect(h.undo).toHaveLength(MAX_HISTORY)
    expect(h.undo[0].index).toBe(5)
    expect(h.undo[h.undo.length - 1].index).toBe(MAX_HISTORY + 4)
  })

  it('跨小節復原：依序跳回各自的小節', () => {
    let h = record(emptyHistory, 0, bar(0))
    h = record(h, 2, bar(2))
    const bars = [{ ...bar(0), edited: true }, bar(1), { ...bar(2), edited: true }]
    const a = undoStep(h, bars)!
    expect(a.index).toBe(2)
    const b = undoStep(a.history, a.bars)!
    expect(b.index).toBe(0)
    expect(b.bars[0].edited).toBeUndefined()
  })
})
