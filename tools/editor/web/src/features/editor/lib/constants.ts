/** 每拍的 tick 數（16 分音符 = 3 tick，三連音 = 4 tick） */
export const TICKS = 12

/** ADTOF 模型的輸出類別 */
export type AdtofClass = 'BD' | 'SD' | 'HH' | 'CY' | 'TM'

export interface RowDef {
  /** 樂器代號（score 的 notes 裡用的） */
  code: string
  /** 顯示名稱 */
  name: string
  /** 格子裡顯示的符號 */
  symbol: string
  /** 對應的 ADTOF 類別（用來顯示模型信心）；沒有對應則為 null */
  cls: AdtofClass | null
}

/** 編輯器格子的樂器列，由上到下 */
export const ROWS: readonly RowDef[] = [
  { code: 'CR', name: 'Crash', symbol: '⊗', cls: 'CY' },
  { code: 'RD', name: 'Ride', symbol: '✕', cls: 'CY' },
  { code: 'HH', name: 'Hi-hat（閉）', symbol: '✕', cls: 'HH' },
  { code: 'HO', name: 'Hi-hat（開）', symbol: '⊙', cls: 'HH' },
  { code: 'TH', name: '高音 Tom', symbol: '●', cls: 'TM' },
  { code: 'TM', name: '中音 Tom', symbol: '●', cls: 'TM' },
  { code: 'SD', name: '小鼓', symbol: '●', cls: 'SD' },
  { code: 'XS', name: 'Cross-stick', symbol: '▲', cls: 'SD' },
  { code: 'TF', name: '落地 Tom', symbol: '●', cls: 'TM' },
  { code: 'BD', name: '大鼓', symbol: '●', cls: 'BD' },
  { code: 'HF', name: 'Hi-hat 踏板', symbol: '✕', cls: null },
]

/** 樂器代號 -> ADTOF 類別 */
export const CLASS_OF: Readonly<Record<string, AdtofClass | null>> = Object.fromEntries(
  ROWS.map((r) => [r.code, r.cls])
)

/** 計算不確定度時走訪的類別順序 */
export const UNSURE_CLASSES: readonly AdtofClass[] = ['BD', 'SD', 'HH', 'CY', 'TM']

/** 同一位置只能留一個的樂器（hi-hat 開/閉） */
export const EXCLUSIVE: Readonly<Record<string, string>> = { HH: 'HO', HO: 'HH' }

/** 每拍 4 個 16 分音符格的標記 */
export const SUB16 = ['', 'e', '&', 'a'] as const
/** 每拍 3 個三連音格的標記 */
export const SUB3 = ['', 'T2', 'T3'] as const

/** 格子欄標題：第 0 格顯示拍號，其餘 16 分用 e & a、三連音用「3連」 */
export function subLabel(beat: number, k: number, triplet: boolean): string {
  if (k === 0) return String(beat + 1)
  return triplet ? '3連' : SUB16[k]
}

/** 格子 tooltip 的位置描述 */
export function subTitle(k: number, triplet: boolean): string {
  return triplet ? ['正拍', '三連第2', '三連第3'][k] : ['正拍', 'e', '&', 'a'][k]
}
