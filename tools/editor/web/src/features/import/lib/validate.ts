/** 扒譜表單的送出前驗證。規則與後端 `projects.clean_source`、`projects.check_name` 一致；
 * 本機路徑檔案是否存在只有後端知道，這裡只擋格式。 */

export type SourceKind = 'empty' | 'url' | 'file' | 'invalid'

export interface SourceCheck {
  kind: SourceKind
  message?: string
}

/** 與後端一樣：去頭尾空白與頭尾的雙引號（從檔案總管「複製為路徑」會帶引號） */
export function normalizeSource(raw: string): string {
  return raw.trim().replace(/^"+|"+$/g, '').trim()
}

export function checkSource(raw: string): SourceCheck {
  const s = normalizeSource(raw)
  if (!s) return { kind: 'empty' }
  if (/^https?:\/\//i.test(s)) return { kind: 'url' }
  if (s.toLowerCase().endsWith('.mp4')) return { kind: 'file' }
  return {
    kind: 'invalid',
    message: '請貼上 http(s) 開頭的影片網址，或以 .mp4 結尾的本機檔案路徑。',
  }
}

export type NameKind = 'empty' | 'ok' | 'invalid' | 'duplicate'

export interface NameCheck {
  kind: NameKind
  message?: string
}

export const NAME_MAX = 80
// eslint-disable-next-line no-control-regex
const ILLEGAL = /[<>:"/\\|?*\x00-\x1f]/
const RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$/i

/** existing：既有專案名稱（Windows 資料夾名稱不分大小寫，所以不分大小寫比對） */
export function checkProjectName(raw: string, existing: readonly string[]): NameCheck {
  const name = raw.trim()
  if (!name) return { kind: 'empty', message: '請替專案取個名稱。' }
  if (name.length > NAME_MAX) {
    return { kind: 'invalid', message: `名稱太長（最多 ${NAME_MAX} 字，目前 ${name.length} 字）。` }
  }
  if (ILLEGAL.test(name)) {
    return { kind: 'invalid', message: '名稱不能包含 < > : " / \\ | ? * 這些字元。' }
  }
  if (name.endsWith('.') || RESERVED.test(name)) {
    return {
      kind: 'invalid',
      message: '名稱不能以句點結尾，也不能用 Windows 保留字（如 CON、NUL）。',
    }
  }
  const key = name.toLowerCase()
  if (existing.some((e) => e.toLowerCase() === key)) {
    return { kind: 'duplicate', message: `已經有名為「${name}」的專案，請換一個名稱。` }
  }
  return { kind: 'ok' }
}

/** 進階選項的數字欄位：空白視為未填（OK）；有填就必須是大於等於 0 的數字 */
export function checkSeconds(raw: string): string | null {
  const s = raw.trim()
  if (!s) return null
  const n = Number(s)
  if (!Number.isFinite(n) || n < 0) return '請輸入 0 或正數（單位：秒）。'
  return null
}
