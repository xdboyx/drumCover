import { describe, expect, it } from 'vitest'
import { checkProjectName, checkSeconds, checkSource, normalizeSource } from './validate'

describe('checkSource', () => {
  it('空白', () => expect(checkSource('  ').kind).toBe('empty'))
  it('http(s) 網址', () => {
    expect(checkSource('https://www.youtube.com/watch?v=abc').kind).toBe('url')
    expect(checkSource('HTTP://x.y').kind).toBe('url')
  })
  it('mp4 路徑，含引號與大小寫', () => {
    expect(checkSource('C:\\影片\\練習.mp4').kind).toBe('file')
    expect(checkSource('"C:\\影片\\練習.MP4"').kind).toBe('file')
  })
  it('其他格式不合法', () => {
    expect(checkSource('abc').kind).toBe('invalid')
    expect(checkSource('C:\\a.mkv').kind).toBe('invalid')
  })
  it('normalizeSource 去引號', () => expect(normalizeSource(' "a.mp4" ')).toBe('a.mp4'))
})

describe('checkProjectName', () => {
  const existing = ['假歌', 'Song A']
  it('空白', () => expect(checkProjectName('  ', existing).kind).toBe('empty'))
  it('合法', () => expect(checkProjectName('夜に駆ける - YOASOBI', existing).kind).toBe('ok'))
  it('非法字元', () => {
    for (const c of '<>:"/\\|?*') expect(checkProjectName(`a${c}b`, existing).kind).toBe('invalid')
  })
  it('太長', () => {
    expect(checkProjectName('字'.repeat(80), existing).kind).toBe('ok')
    expect(checkProjectName('字'.repeat(81), existing).kind).toBe('invalid')
  })
  it('句點結尾與保留字', () => {
    expect(checkProjectName('abc.', existing).kind).toBe('invalid')
    expect(checkProjectName('NUL', existing).kind).toBe('invalid')
    expect(checkProjectName('com1.txt', existing).kind).toBe('invalid')
  })
  it('與既有專案同名（不分大小寫、忽略頭尾空白）', () => {
    expect(checkProjectName(' 假歌 ', existing).kind).toBe('duplicate')
    expect(checkProjectName('song a', existing).kind).toBe('duplicate')
  })
})

describe('checkSeconds', () => {
  it('空白、數字合法', () => {
    expect(checkSeconds('')).toBeNull()
    expect(checkSeconds('12.5')).toBeNull()
  })
  it('負數與非數字不合法', () => {
    expect(checkSeconds('-1')).not.toBeNull()
    expect(checkSeconds('abc')).not.toBeNull()
  })
})
