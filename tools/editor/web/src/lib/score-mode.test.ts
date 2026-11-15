import { describe, expect, it } from 'vitest'
import { SCORE_MODE_OPTIONS, scoreModeName } from './score-mode'

describe('scoreModeName', () => {
  it('加強顯示加強，基本與沒有 mode 的舊資料都顯示基本', () => {
    expect(scoreModeName('enhanced')).toBe('加強')
    expect(scoreModeName('basic')).toBe('基本')
    expect(scoreModeName(undefined)).toBe('基本')
  })
})

describe('SCORE_MODE_OPTIONS', () => {
  it('第一個是預設的基本', () => {
    expect(SCORE_MODE_OPTIONS[0].value).toBe('basic')
  })
})
