import type { VersionInfo, VersionWarning } from '@/lib/types'

/** AI 譜與舊 AI 譜唯讀（伺服器也會擋）。版本清單還沒載入時，只有 "ai" 確定唯讀。 */
export function isReadOnlyVersion(
  id: string,
  versions: readonly VersionInfo[] | undefined
): boolean {
  return id === 'ai' || versions?.find((v) => v.id === id)?.kind === 'old_ai'
}

/** 版本選單上的名稱 */
export function versionLabel(v: VersionInfo): string {
  const base =
    v.kind === 'ai' ? 'AI 譜（唯讀）' : v.kind === 'old_ai' ? `${v.name}（唯讀）` : v.name
  return `${base}${v.source_deleted ? '（來源已刪除）' : ''}${v.warning ? ' ⚠' : ''}`
}

/** 對齊警告的完整說明，含小節編號（1 起算） */
export function warningText(w: VersionWarning): string {
  return `${w.message}（第 ${w.bars.map((i) => i + 1).join('、')} 小節）`
}
