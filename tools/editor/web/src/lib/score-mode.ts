import type { ScoreMode } from './types'

export const SCORE_MODE_OPTIONS: { value: ScoreMode; label: string }[] = [
  { value: 'basic', label: '基本' },
  { value: 'enhanced', label: '加強（實驗中）' },
]

export const SCORE_MODE_HINT =
  '基本是固定不變的原始辨識方法；加強會套用實驗中的修正，目前與基本相同。'

/** 顯示用的短名稱；沒有 mode（舊資料）視為基本 */
export function scoreModeName(mode: ScoreMode | undefined): string {
  return mode === 'enhanced' ? '加強' : '基本'
}
