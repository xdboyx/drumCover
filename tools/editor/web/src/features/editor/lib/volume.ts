/** 音量限制在 0–1；非數字退回 fallback */
export function clampVolume(v: number, fallback = 1): number {
  if (!Number.isFinite(v)) return fallback
  return Math.min(1, Math.max(0, v))
}

/** 0–1 的音量換成 0–100 的整數百分比 */
export function volumeToPercent(v: number): number {
  return Math.round(clampVolume(v) * 100)
}

/** 0–100 的百分比換成 0–1 的音量 */
export function percentToVolume(p: number): number {
  return clampVolume(p / 100)
}

/** 兩個音量是否視為相同（避免浮點誤差造成來回寫入） */
export function sameVolume(a: number, b: number): boolean {
  return Math.abs(a - b) < 0.005
}
