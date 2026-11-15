import { describe, expect, it } from 'vitest'
import { clampVolume, percentToVolume, sameVolume, volumeToPercent } from './volume'

describe('clampVolume', () => {
  it('範圍內不變，超出就夾住', () => {
    expect(clampVolume(0.4)).toBe(0.4)
    expect(clampVolume(-1)).toBe(0)
    expect(clampVolume(3)).toBe(1)
  })
  it('非數字用 fallback', () => {
    expect(clampVolume(NaN, 0.7)).toBe(0.7)
    expect(clampVolume(Infinity, 0.7)).toBe(0.7)
  })
})

describe('百分比換算', () => {
  it('音量轉百分比（四捨五入成整數）', () => {
    expect(volumeToPercent(0.7)).toBe(70)
    expect(volumeToPercent(0.333)).toBe(33)
    expect(volumeToPercent(2)).toBe(100)
  })
  it('百分比轉音量', () => {
    expect(percentToVolume(70)).toBe(0.7)
    expect(percentToVolume(150)).toBe(1)
    expect(percentToVolume(-5)).toBe(0)
  })
})

describe('sameVolume', () => {
  it('差距極小視為相同', () => {
    expect(sameVolume(0.5, 0.5001)).toBe(true)
    expect(sameVolume(0.5, 0.6)).toBe(false)
  })
})
