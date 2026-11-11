import { beforeEach, describe, expect, it } from 'vitest'
import type { Bar, Score } from '@/lib/types'
import { toggleNote } from './lib/bar'
import { useEditorStore } from './store'

const bar = (n: number): Bar => ({ t0: n * 2, t1: n * 2 + 2, ticks: 48, events: [] })
const score = (n = 4): Score => ({ bpm: 120, bars: Array.from({ length: n }, (_, i) => bar(i)) })
const payload = (project: string, version: string, media: string[] = ['video.mp4']) => ({
  project,
  version,
  score: score(),
  act: null,
  media,
})

const s = () => useEditorStore.getState()

beforeEach(() => {
  s().reset()
})

describe('load', () => {
  it('換專案回到第 0 小節，同專案切版本保留目前小節', () => {
    s().load(payload('a', 'ai'))
    s().setCur(2)
    s().load(payload('a', 'v1'))
    expect(s().cur).toBe(2)
    s().load(payload('b', 'ai'))
    expect(s().cur).toBe(0)
  })

  it('保留的小節不會超出新鼓譜的範圍', () => {
    s().load(payload('a', 'ai'))
    s().setCur(3)
    s().load({ ...payload('a', 'v1'), score: score(2) })
    expect(s().cur).toBe(1)
  })

  it('載入會清掉未存狀態與復原紀錄；沒有 drums.wav 時音源改回原曲', () => {
    s().load(payload('a', 'v1', ['video.mp4', 'drums.wav']))
    s().setSource('drums')
    s().editBar((b) => toggleNote(b, 0, 'BD'))
    expect(s().dirty).toBe(true)
    s().load(payload('a', 'v1', ['video.mp4']))
    expect(s().dirty).toBe(false)
    expect(s().history.undo).toHaveLength(0)
    expect(s().source).toBe('mix')
  })
})

describe('editBar / undo / redo', () => {
  it('修改目前小節、標記 dirty、可復原重做，復原會跳到該小節', () => {
    s().load(payload('a', 'v1'))
    s().setCur(2)
    s().editBar((b) => toggleNote(b, 0, 'BD'))
    expect(s().score!.bars[2].events).toHaveLength(1)
    expect(s().score!.bars[2].edited).toBe(true)
    s().setCur(0)
    s().undo()
    expect(s().cur).toBe(2)
    expect(s().score!.bars[2].events).toHaveLength(0)
    s().setCur(1)
    s().redo()
    expect(s().cur).toBe(2)
    expect(s().score!.bars[2].events).toHaveLength(1)
  })

  it('每次內容變動版次都會增加（預覽快取靠它作廢）', () => {
    s().load(payload('a', 'v1'))
    const r0 = s().rev
    s().editBar((b) => toggleNote(b, 0, 'BD'))
    const r1 = s().rev
    s().undo()
    expect(r1).toBeGreaterThan(r0)
    expect(s().rev).toBeGreaterThan(r1)
  })
})

describe('markSaved', () => {
  it('儲存期間沒有新修改：換成伺服器版並清掉 dirty', () => {
    s().load(payload('a', 'v1'))
    s().editBar((b) => toggleNote(b, 0, 'BD'))
    const fresh = score()
    s().markSaved(fresh, s().rev)
    expect(s().dirty).toBe(false)
    expect(s().score).toBe(fresh)
  })

  it('儲存期間又改過：保留記憶體中的鼓譜，仍然是有未存修改', () => {
    s().load(payload('a', 'v1'))
    s().editBar((b) => toggleNote(b, 0, 'BD'))
    const revAtSave = s().rev
    s().editBar((b) => toggleNote(b, 3, 'SD'))
    s().markSaved(score(), revAtSave)
    expect(s().dirty).toBe(true)
    expect(s().score!.bars[0].events).toHaveLength(2)
  })
})

describe('copyBar', () => {
  it('複製目前小節的內容到剪貼簿', () => {
    s().load(payload('a', 'v1'))
    s().editBar((b) => toggleNote(b, 0, 'BD'))
    s().copyBar()
    expect(s().clip?.events).toEqual([{ tick: 0, notes: ['BD'] }])
  })
})
