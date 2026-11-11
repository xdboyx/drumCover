import { describe, expect, it } from 'vitest'
import type { Bar } from '@/lib/types'
import { barBeats, barStartTime, formatTime, playheadPosition } from './playhead'

const bar = (extra: Partial<Bar> = {}): Bar => ({ t0: 10, t1: 12, ticks: 48, events: [], ...extra })

describe('barBeats', () => {
  it('有 beats 就用 beats', () => {
    const beats = [10, 10.4, 10.9, 11.5, 12]
    expect(barBeats(bar({ beats }))).toBe(beats)
  })
  it('沒有 beats 就均分', () => {
    expect(barBeats(bar())).toEqual([10, 10.5, 11, 11.5, 12])
  })
})

describe('playheadPosition', () => {
  const b = bar({ beats: [10, 10.4, 10.9, 11.5, 12] })
  it('依實際拍點分段，不是均分', () => {
    const first = playheadPosition(b, 10.2)!
    expect(first.beat).toBe(0)
    expect(first.frac).toBeCloseTo(0.5)
    const p = playheadPosition(b, 10.9)!
    expect(p.beat).toBe(2)
    expect(p.frac).toBe(0)
  })
  it('小節外回傳 null', () => {
    expect(playheadPosition(b, 9.9)).toBeNull()
    expect(playheadPosition(b, 12.1)).toBeNull()
  })
  it('小節終點落在最後一拍的 1', () => {
    expect(playheadPosition(b, 12)).toEqual({ beat: 3, frac: 1 })
  })
  it('拍長為 0 不會變 NaN', () => {
    const z = bar({ beats: [10, 10, 11, 11.5, 12] })
    expect(playheadPosition(z, 10)!.frac).toBe(0)
  })
})

describe('barStartTime', () => {
  it('提前一拍', () => {
    expect(barStartTime(bar({ beats: [10, 10.5, 11, 11.5, 12] }), true)).toBeCloseTo(9.5)
  })
  it('不提前一拍時只提前 0.05 秒', () => {
    expect(barStartTime(bar(), false)).toBeCloseTo(9.95)
  })
  it('不會小於 0', () => {
    expect(barStartTime(bar({ t0: 0.1, t1: 2.1 }), true)).toBe(0)
  })
})

describe('formatTime', () => {
  it('格式為 m:ss.ss', () => {
    expect(formatTime(65.5)).toBe('1:05.50')
    expect(formatTime(0)).toBe('0:00.00')
  })
})
