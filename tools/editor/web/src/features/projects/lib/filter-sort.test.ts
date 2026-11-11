import { describe, expect, it } from 'vitest'
import type { ProjectListItem } from '@/lib/types'
import { filterAndSort } from './filter-sort'
import { formatDuration, formatRelative, projectMeta } from './format'

const mk = (name: string, updated?: string): ProjectListItem => ({
  name,
  status: 'ready',
  error: null,
  updated,
})
const items = [
  mk('b 歌', '2026-01-02T00:00:00'),
  mk('A song', '2026-01-03T00:00:00'),
  mk('c 歌', '2026-01-01T00:00:00'),
  mk('進行中'),
]

describe('filterAndSort', () => {
  it('最近更新：新到舊，沒有時間的排最前', () => {
    expect(filterAndSort(items, '', 'updated').map((p) => p.name)).toEqual([
      '進行中',
      'A song',
      'b 歌',
      'c 歌',
    ])
  })
  it('名稱排序', () => {
    // 中文與英文誰先依系統語系，這裡只驗證英文之間的順序
    const names = filterAndSort(items, '', 'name').map((p) => p.name)
    expect(names.indexOf('A song')).toBeLessThan(names.indexOf('b 歌'))
    expect(names.indexOf('b 歌')).toBeLessThan(names.indexOf('c 歌'))
  })
  it('過濾不分大小寫', () => {
    expect(filterAndSort(items, '  SONG ', 'name').map((p) => p.name)).toEqual(['A song'])
  })
  it('不改動原陣列', () => {
    const copy = [...items]
    filterAndSort(items, '', 'name')
    expect(items).toEqual(copy)
  })
})

describe('format', () => {
  it('formatDuration', () => {
    expect(formatDuration(205.4)).toBe('3:25')
    expect(formatDuration(5)).toBe('0:05')
  })
  it('formatRelative', () => {
    const now = Date.parse('2026-01-10T12:00:00')
    expect(formatRelative('2026-01-10T11:59:30', now)).toBe('剛剛')
    expect(formatRelative('2026-01-10T11:00:00', now)).toBe('1 小時前')
    expect(formatRelative('2026-01-09T08:00:00', now)).toBe('昨天')
    expect(formatRelative('2026-01-01T08:00:00', now)).toBe('9 天前')
    expect(formatRelative(undefined, now)).toBe('')
    expect(formatRelative('壞的', now)).toBe('')
  })
  it('projectMeta 略過沒資料的欄位', () => {
    expect(projectMeta(mk('x'))).toEqual([])
    expect(projectMeta({ ...mk('x'), bpm: 120.4, bars: 64, duration: 205, versions: 2 })).toEqual([
      'BPM 120',
      '64 小節',
      '3:25',
      '2 個編輯版本',
    ])
  })
})
