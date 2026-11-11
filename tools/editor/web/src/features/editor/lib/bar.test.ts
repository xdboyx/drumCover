import { describe, expect, it } from 'vitest'
import type { Bar } from '@/lib/types'
import {
  applyBarContent,
  barIndexAt,
  barContent,
  clearBar,
  hasNote,
  isTripletBeat,
  restoreBarContent,
  tickTime,
  toggleNote,
  toggleTriplet,
} from './bar'

const bar = (events: Bar['events'] = [], extra: Partial<Bar> = {}): Bar => ({
  t0: 10,
  t1: 12,
  ticks: 48,
  events,
  ...extra,
})

describe('isTripletBeat / hasNote', () => {
  it('明確標記的拍是三連音', () => {
    expect(isTripletBeat(bar([], { triplets: [2] }), 2)).toBe(true)
    expect(isTripletBeat(bar([], { triplets: [2] }), 1)).toBe(false)
  })
  it('有不在 16 分格線上的音也算三連音', () => {
    const b = bar([{ tick: 12 + 4, notes: ['SD'] }])
    expect(isTripletBeat(b, 1)).toBe(true)
    expect(isTripletBeat(b, 0)).toBe(false)
  })
  it('hasNote', () => {
    const b = bar([{ tick: 6, notes: ['HH', 'BD'] }])
    expect(hasNote(b, 6, 'BD')).toBe(true)
    expect(hasNote(b, 6, 'SD')).toBe(false)
    expect(hasNote(b, 3, 'BD')).toBe(false)
  })
})

describe('toggleNote', () => {
  it('新增音並標記 edited，不修改原物件', () => {
    const b = bar()
    const n = toggleNote(b, 0, 'BD')
    expect(n.events).toEqual([{ tick: 0, notes: ['BD'] }])
    expect(n.edited).toBe(true)
    expect(b.events).toEqual([])
    expect(b.edited).toBeUndefined()
  })
  it('再點一次移除，空事件被清掉', () => {
    const n = toggleNote(toggleNote(bar(), 0, 'BD'), 0, 'BD')
    expect(n.events).toEqual([])
  })
  it('事件依 tick 排序', () => {
    let n = toggleNote(bar(), 9, 'SD')
    n = toggleNote(n, 3, 'HH')
    expect(n.events.map((e) => e.tick)).toEqual([3, 9])
  })
  it('hi-hat 開/閉互斥', () => {
    let n = toggleNote(bar(), 0, 'HH')
    n = toggleNote(n, 0, 'HO')
    expect(n.events[0].notes).toEqual(['HO'])
    n = toggleNote(n, 0, 'HH')
    expect(n.events[0].notes).toEqual(['HH'])
  })
  it('其他樂器可以疊在同一格', () => {
    let n = toggleNote(bar(), 0, 'HH')
    n = toggleNote(n, 0, 'BD')
    expect(n.events[0].notes).toEqual(['HH', 'BD'])
  })
  it('不改到原本事件物件', () => {
    const b = bar([{ tick: 0, notes: ['BD'], t: 10, idx: 0 }])
    toggleNote(b, 0, 'SD')
    expect(b.events[0].notes).toEqual(['BD'])
  })
})

describe('toggleTriplet', () => {
  it('16 分 -> 三連：3 與 6 合併到 4，9 到 8', () => {
    const b = bar([
      { tick: 0, notes: ['BD'] },
      { tick: 3, notes: ['HH'] },
      { tick: 6, notes: ['SD'] },
      { tick: 9, notes: ['HH'] },
    ])
    const n = toggleTriplet(b, 0)
    expect(n.triplets).toEqual([0])
    expect(n.events).toEqual([
      { tick: 0, notes: ['BD'] },
      { tick: 4, notes: ['HH', 'SD'] },
      { tick: 8, notes: ['HH'] },
    ])
    expect(n.edited).toBe(true)
  })
  it('三連 -> 16 分：4 到 3，8 到 9', () => {
    const b = bar(
      [
        { tick: 0, notes: ['BD'] },
        { tick: 4, notes: ['HH'] },
        { tick: 8, notes: ['HH'] },
      ],
      { triplets: [0] }
    )
    const n = toggleTriplet(b, 0)
    expect(n.triplets).toEqual([])
    expect(n.events.map((e) => e.tick)).toEqual([0, 3, 9])
  })
  it('只動指定的那一拍', () => {
    const b = bar([
      { tick: 3, notes: ['HH'] },
      { tick: 15, notes: ['HH'] },
    ])
    const n = toggleTriplet(b, 1)
    expect(n.events.map((e) => e.tick)).toEqual([3, 16])
    expect(n.triplets).toEqual([1])
  })
  it('沒有標記但事件在三連格上（隱含三連）也能切回 16 分', () => {
    const b = bar([{ tick: 4, notes: ['HH'] }])
    expect(isTripletBeat(b, 0)).toBe(true)
    const n = toggleTriplet(b, 0)
    expect(n.events.map((e) => e.tick)).toEqual([3])
    expect(isTripletBeat(n, 0)).toBe(false)
  })
  it('不修改原物件', () => {
    const b = bar([{ tick: 3, notes: ['HH'] }], { triplets: [] })
    toggleTriplet(b, 0)
    expect(b.events[0].tick).toBe(3)
    expect(b.triplets).toEqual([])
  })
})

describe('小節內容 複製 / 貼上 / 清空 / 還原', () => {
  const src = bar([{ tick: 0, notes: ['BD'], t: 10, idx: 5 }], { triplets: [1], edited: false })
  it('barContent 只留 tick/notes/triplets，且是深拷貝', () => {
    const c = barContent(src)
    expect(c).toEqual({ events: [{ tick: 0, notes: ['BD'] }], triplets: [1] })
    c.events[0].notes.push('SD')
    expect(src.events[0].notes).toEqual(['BD'])
  })
  it('applyBarContent 取代內容並標記 edited，保留時間資訊', () => {
    const target = bar([{ tick: 6, notes: ['SD'] }])
    const n = applyBarContent(target, barContent(src))
    expect(n.events).toEqual([{ tick: 0, notes: ['BD'] }])
    expect(n.triplets).toEqual([1])
    expect(n.edited).toBe(true)
    expect(n.t0).toBe(10)
    expect(target.events[0].tick).toBe(6)
  })
  it('clearBar', () => {
    const n = clearBar(src)
    expect(n.events).toEqual([])
    expect(n.triplets).toEqual([])
    expect(n.edited).toBe(true)
  })
  it('restoreBarContent 拿掉 edited，slot 換算成 tick', () => {
    const b = bar([{ tick: 1, notes: ['HH'] }], { edited: true, triplets: [0] })
    const n = restoreBarContent(b, { events: [{ slot: 2, notes: ['BD'] }, { tick: 9, notes: ['SD'] }] })
    expect(n.events).toEqual([
      { tick: 6, notes: ['BD'] },
      { tick: 9, notes: ['SD'] },
    ])
    expect(n.triplets).toEqual([])
    expect('edited' in n).toBe(false)
    expect(b.edited).toBe(true)
  })
})

describe('tickTime', () => {
  it('沒有 beats：依小節頭尾均分', () => {
    expect(tickTime(bar(), 0)).toBe(10)
    expect(tickTime(bar(), 24)).toBe(11)
    expect(tickTime(bar(), 48)).toBe(12)
  })
  it('有 beats：每拍內線性內插', () => {
    const b = bar([], { beats: [10, 10.5, 11.25, 11.5, 12] })
    expect(tickTime(b, 0)).toBe(10)
    expect(tickTime(b, 6)).toBeCloseTo(10.25)
    expect(tickTime(b, 12)).toBeCloseTo(10.5)
    expect(tickTime(b, 12 + 6)).toBeCloseTo(10.875)
    expect(tickTime(b, 36)).toBeCloseTo(11.5)
  })
})

describe('barIndexAt', () => {
  const bars = [{ t0: 1.5 }, { t0: 3 }, { t0: 4.5 }] as never[]
  it('回傳最後一個起點 ≤ t 的小節', () => {
    expect(barIndexAt(bars, 0)).toBe(0)
    expect(barIndexAt(bars, 3.2)).toBe(1)
    expect(barIndexAt(bars, 99)).toBe(2)
  })
  it('容許 currentTime 被截斷的誤差', () => {
    expect(barIndexAt(bars, 2.999999)).toBe(1)
  })
})
