import { describe, expect, it } from 'vitest'
import { overallProgress } from './job-progress'

describe('overallProgress', () => {
  const steps = ['下載', '分離鼓聲', '扒譜', '排版']
  it('第一步一半', () => {
    expect(overallProgress({ steps, step_index: 0, progress: 0.5 })).toBeCloseTo(0.125)
  })
  it('第三步開始', () => {
    expect(overallProgress({ steps, step_index: 2, progress: 0 })).toBeCloseTo(0.5)
  })
  it('超出範圍會被夾住', () => {
    expect(overallProgress({ steps, step_index: 9, progress: 5 })).toBe(1)
  })
  it('沒有步驟時用目前進度', () => {
    expect(overallProgress({ progress: 0.3 })).toBe(0.3)
    expect(overallProgress({})).toBe(0)
  })
})
