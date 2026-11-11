import { describe, expect, it } from 'vitest'
import type { Act, ActRow, Bar } from '@/lib/types'
import { barUnsure, cellAct, cellUnsure } from './confidence'

const zeros = (n: number) => Array<number>(n).fill(0)
const emptyRow = (): ActRow => ({
  BD: { s16: zeros(16), t3: zeros(12) },
  SD: { s16: zeros(16), t3: zeros(12) },
  HH: { s16: zeros(16), t3: zeros(12) },
  CY: { s16: zeros(16), t3: zeros(12) },
  TM: { s16: zeros(16), t3: zeros(12) },
})
const bar = (events: Bar['events'] = [], extra: Partial<Bar> = {}): Bar => ({
  t0: 0,
  t1: 2,
  ticks: 48,
  events,
  ...extra,
})

describe('cellAct', () => {
  it('沒有 act / 類別 / 該小節時回傳 0', () => {
    expect(cellAct(null, 0, 'BD', 0, 0, false)).toBe(0)
    expect(cellAct([emptyRow()], 0, null, 0, 0, false)).toBe(0)
    expect(cellAct([emptyRow()], 3, 'BD', 0, 0, false)).toBe(0)
  })
  it('16 分用 s16[j*4+k]，三連音用 t3[j*3+k]', () => {
    const row = emptyRow()
    row.SD.s16[6] = 0.7 // 第 1 拍第 2 格
    row.SD.t3[5] = 0.4 // 第 1 拍第 2 格
    expect(cellAct([row], 0, 'SD', 1, 2, false)).toBe(0.7)
    expect(cellAct([row], 0, 'SD', 1, 2, true)).toBe(0.4)
  })
})

describe('cellUnsure', () => {
  it('沒有 act 一律不確定度 false', () => {
    expect(cellUnsure(null, 0, bar([{ tick: 0, notes: ['BD'] }]), 'BD', 0, true)).toBe(false)
  })
  it('沒有對應 ADTOF 類別的樂器（HF）永遠 false', () => {
    expect(cellUnsure([emptyRow()], 0, bar([{ tick: 0, notes: ['HF'] }]), 'HF', 0, true)).toBe(false)
  })
  it('有寫音：機率 < 0.3 不確定，>= 0.3 確定', () => {
    const row = emptyRow()
    const b = bar([{ tick: 0, notes: ['BD'] }])
    row.BD.s16[0] = 0.29
    expect(cellUnsure([row], 0, b, 'BD', 0, true)).toBe(true)
    row.BD.s16[0] = 0.3
    expect(cellUnsure([row], 0, b, 'BD', 0, true)).toBe(false)
  })
  it('沒寫音：機率 >= 0.2 不確定，< 0.2 確定', () => {
    const row = emptyRow()
    const b = bar()
    row.SD.s16[0] = 0.2
    expect(cellUnsure([row], 0, b, 'SD', 0, false)).toBe(true)
    row.SD.s16[0] = 0.19
    expect(cellUnsure([row], 0, b, 'SD', 0, false)).toBe(false)
  })
  it('沒寫音但同類別其他樂器已寫在這格（XS 與 SD）不算', () => {
    const row = emptyRow()
    row.SD.s16[0] = 0.9
    const b = bar([{ tick: 0, notes: ['XS'] }])
    expect(cellUnsure([row], 0, b, 'SD', 0, false)).toBe(false)
  })
  it('三連音拍用 t3：tick 4 對應第 1 格', () => {
    const row = emptyRow()
    row.BD.t3[1] = 0.9
    const b = bar([{ tick: 4, notes: ['BD'] }])
    expect(cellUnsure([row], 0, b, 'BD', 4, true)).toBe(false)
    row.BD.t3[1] = 0.1
    expect(cellUnsure([row], 0, b, 'BD', 4, true)).toBe(true)
  })
})

describe('barUnsure', () => {
  it('空小節且沒有 act：0', () => {
    expect(barUnsure(null, 0, bar())).toBe(0)
  })
  it('有音但沒有 act：0', () => {
    expect(barUnsure(null, 0, bar([{ tick: 0, notes: ['BD'] }]))).toBe(0)
  })
  it('全 0 機率的空小節：0；寫了機率為 0 的音：每個音算 1 處', () => {
    const act: Act = [emptyRow()]
    expect(barUnsure(act, 0, bar())).toBe(0)
    const b = bar([
      { tick: 0, notes: ['BD'] },
      { tick: 6, notes: ['SD'] },
    ])
    expect(barUnsure(act, 0, b)).toBe(2)
  })
  it('AI 有反應但沒寫：算一處', () => {
    const row = emptyRow()
    row.HH.s16[2] = 0.5
    expect(barUnsure([row], 0, bar())).toBe(1)
  })
  it('用 i 取對應小節的 act', () => {
    const quiet = emptyRow()
    const loud = emptyRow()
    loud.BD.s16[0] = 1
    expect(barUnsure([quiet, loud], 1, bar())).toBe(1)
    expect(barUnsure([quiet, loud], 0, bar())).toBe(0)
  })
  it('三連音拍每拍走 3 格而不是 4 格', () => {
    const row = emptyRow()
    row.BD.t3[2] = 0.5 // 第 0 拍三連第 3 格
    row.BD.s16[3] = 0.5 // 若誤用 16 分會多算
    expect(barUnsure([row], 0, bar([], { triplets: [0] }))).toBe(1)
  })
})
