import { describe, expect, it } from 'vitest'
import { cursorX, lineIndexAt, restingCursorX, TIME_EPS } from './preview'

// 一行有兩個小節：第 1 小節 t0=2.0（音 2.0 / 2.5 / 3.0），第 2 小節 t0=4.0（音 4.0 / 4.5）
const line = {
  t0: 2.0,
  evs: [
    [2.0, 100],
    [2.5, 150],
    [3.0, 200],
    [4.0, 300],
    [4.5, 350],
  ] as [number, number][],
}

describe('cursorX', () => {
  it('t 比第 2 小節第一個音小 1e-6：游標在該音，不是上一小節最後一個', () => {
    expect(cursorX(line, 4.0 - 1e-6)).toBe(300)
  })
  it('t 比第 1 小節第一個音小 1e-6：有游標（不是 null）', () => {
    expect(cursorX(line, 2.0 - 1e-6)).toBe(100)
  })
  it('微秒截斷的實際例子', () => {
    const l = { t0: 9.161234567, evs: [[9.161234567, 42]] as [number, number][] }
    expect(cursorX(l, 9.161234)).toBe(42)
  })
  it('正常播放中游標停在最近一個已到達的音', () => {
    expect(cursorX(line, 2.2)).toBe(100)
    expect(cursorX(line, 2.5)).toBe(150)
    expect(cursorX(line, 3.4)).toBe(200)
    expect(cursorX(line, 3.99)).toBe(200)
    expect(cursorX(line, 4.2)).toBe(300)
    expect(cursorX(line, 99)).toBe(350)
  })
  it('t 遠早於第一個音時回 null', () => {
    expect(cursorX(line, 1.0)).toBeNull()
    expect(cursorX(line, 2.0 - 0.02)).toBeNull()
  })
  it('進入這一行但第一個音還沒到：null', () => {
    const l = { t0: 5.0, evs: [[5.3, 10]] as [number, number][] }
    expect(cursorX(l, 5.0)).toBeNull()
    expect(cursorX(l, 5.3)).toBe(10)
  })
  it('容許誤差不會讓游標提早超過 TIME_EPS', () => {
    expect(cursorX(line, 2.5 - TIME_EPS * 2)).toBe(100)
  })
  it('沒有音：null', () => {
    expect(cursorX({ t0: 0, evs: [] }, 1)).toBeNull()
  })
})

describe('lineIndexAt', () => {
  const lines: [number, number][] = [
    [0, 4],
    [4, 8],
    [8, 12],
  ]
  it('t 比某行起點小 1e-6 仍選那一行', () => {
    expect(lineIndexAt(lines, 4 - 1e-6)).toBe(1)
    expect(lineIndexAt(lines, 8 - 1e-6)).toBe(2)
  })
  it('一般情況', () => {
    expect(lineIndexAt(lines, 0)).toBe(0)
    expect(lineIndexAt(lines, 3.9)).toBe(0)
    expect(lineIndexAt(lines, 4)).toBe(1)
    expect(lineIndexAt(lines, 11)).toBe(2)
    expect(lineIndexAt(lines, 100)).toBe(2)
  })
  it('比第一行起點還早，仍回傳第 0 行', () => {
    expect(lineIndexAt([[5, 9]], 1)).toBe(0)
  })
  it('沒有行回傳 0', () => {
    expect(lineIndexAt([], 3)).toBe(0)
  })
})

describe('restingCursorX', () => {
  // 小節 A：x 0–200、t0=2（第一個音在第 3 拍 t=3.0）；小節 B：x 200–400、t0=4（音 4.0）；小節 C：x 400–600、t0=6 沒有音
  const L = {
    t0: 2.0,
    t1: 8.0,
    evs: [
      [3.0, 120],
      [3.5, 160],
      [4.0, 250],
    ] as [number, number][],
    measures: [
      { x0: 0, x1: 200, bar: 0, t0: 2.0 },
      { x0: 200, x1: 400, bar: 1, t0: 4.0 },
      { x0: 400, x1: 600, bar: 2, t0: 6.0 },
    ],
  }
  it('小節第一個音在第 3 拍：停在該小節第一個音', () => {
    expect(restingCursorX(L, 2.0)).toBe(120)
    expect(restingCursorX(L, 2.0 - 1e-6)).toBe(120)
  })
  it('第一個小節同樣情況不是 null', () => {
    expect(cursorX(L, 2.0)).toBeNull()
    expect(restingCursorX(L, 2.0)).not.toBeNull()
  })
  it('第二小節起點沒有音可選上一小節：落在第二小節第一個音', () => {
    const l = { ...L, evs: [[3.0, 120], [4.5, 260]] as [number, number][] }
    expect(cursorX(l, 4.0)).toBe(120)
    expect(restingCursorX(l, 4.0)).toBe(260)
    expect(restingCursorX(l, 4.0 - 1e-6)).toBe(260)
  })
  it('小節第一拍就有音：與 cursorX 相同', () => {
    expect(restingCursorX(L, 4.0)).toBe(cursorX(L, 4.0))
    expect(restingCursorX(L, 4.0 - 1e-6)).toBe(250)
  })
  it('整小節沒有音：與 cursorX 相同', () => {
    expect(restingCursorX(L, 6.0)).toBe(cursorX(L, 6.0))
  })
  it('t 在小節中段且已有音到達：與 cursorX 相同', () => {
    expect(restingCursorX(L, 3.7)).toBe(160)
    expect(restingCursorX(L, 3.7)).toBe(cursorX(L, 3.7))
  })
})
