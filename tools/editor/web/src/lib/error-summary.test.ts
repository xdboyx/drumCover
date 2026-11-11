import { describe, expect, it } from 'vitest'
import { summarizeError } from './error-summary'

describe('summarizeError', () => {
  it('單行不需展開', () => {
    expect(summarizeError('找不到影片')).toEqual({ summary: '找不到影片', hasMore: false })
  })
  it('多行取最後一行並可展開', () => {
    const r = summarizeError('Traceback...\n  File x\nRuntimeError: 下載失敗\n')
    expect(r).toEqual({ summary: 'RuntimeError: 下載失敗', hasMore: true })
  })
  it('過長截斷', () => {
    const r = summarizeError('字'.repeat(200), 50)
    expect(r.summary).toHaveLength(50)
    expect(r.hasMore).toBe(true)
  })
  it('空字串', () => {
    expect(summarizeError('')).toEqual({ summary: '', hasMore: false })
  })
})
