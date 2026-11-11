import type { ProjectListItem } from '@/lib/types'

/** 秒數 → 「3:25」 */
export function formatDuration(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** ISO 時間 → 「剛剛／5 分鐘前／3 小時前／昨天／12 天前／2026-03-01」；無法解析回傳空字串 */
export function formatRelative(iso: string | undefined | null, now = Date.now()): string {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const diff = Math.max(0, now - t) / 1000
  if (diff < 60) return '剛剛'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分鐘前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小時前`
  const days = Math.floor(diff / 86400)
  if (days === 1) return '昨天'
  if (days < 30) return `${days} 天前`
  return new Date(t).toLocaleDateString('sv-SE')
}

/** 專案列的辨識資訊：「BPM 120・64 小節・3:25・2 個編輯版本」；沒有資料的欄位略過 */
export function projectMeta(p: ProjectListItem): string[] {
  const out: string[] = []
  if (p.bpm != null) out.push(`BPM ${Math.round(p.bpm)}`)
  if (p.bars != null) out.push(`${p.bars} 小節`)
  if (p.duration != null) out.push(formatDuration(p.duration))
  if (p.versions != null) out.push(p.versions > 0 ? `${p.versions} 個編輯版本` : '尚無編輯版本')
  return out
}
