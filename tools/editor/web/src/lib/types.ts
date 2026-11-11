// 依 tools/editor/server.py 的實際回應定義。

export interface ScoreEvent {
  /** 小節內的 tick（每拍 12 tick；16 分音符 = 3 tick 倍數，三連音 = 4 tick 倍數） */
  tick: number
  /** 樂器代號（見 features/editor/lib/constants 的 ROWS） */
  notes: string[]
  /** 伺服器依 tick 重算的秒數（編輯中的新事件沒有） */
  t?: number
  /** 全曲事件編號（編輯中的新事件沒有） */
  idx?: number
}

export interface Bar {
  t0: number
  t1: number
  /** 每拍起點的秒數（拍數 + 1 個）；舊資料可能沒有 */
  beats?: number[]
  ticks: number
  events: ScoreEvent[]
  /** 使用者手動修改過 */
  edited?: boolean
  /** 以三連音記譜的拍（0 起算） */
  triplets?: number[]
}

export interface ScoreMeta {
  name?: string
  kind?: string
  source?: string | null
  created?: string
  [k: string]: unknown
}

export interface Score {
  bpm: number
  meter?: unknown
  duration?: number
  offset_ms?: number
  bars: Bar[]
  meta?: ScoreMeta
}

export type VersionKind = 'ai' | 'old_ai' | 'edited'

export interface VersionWarning {
  old_ai: string
  /** 對不齊的小節（0 起算） */
  bars: number[]
  message: string
}

export interface VersionInfo {
  id: string
  name: string
  kind: VersionKind
  source: string | null
  created: string | null
  source_deleted: boolean
  warning?: VersionWarning
}

/** 每小節、每個 ADTOF 類別的擊打機率：s16 有 16 格、t3 有 12 格（4 拍時；依拍數成比例） */
export interface BarActivation {
  s16: number[]
  t3: number[]
}
export type ActRow = Record<string, BarActivation>
/** 每小節一筆；沒有機率曲線檔時為 null */
export type Act = ActRow[] | null

export interface ScoreResponse {
  score: Score
  version: string
  act: Act
  media: string[]
}

export type JobKind = 'import' | 'reimport' | 'render'
export type JobState = 'idle' | 'running' | 'done' | 'error'

export interface JobStatus {
  state: JobState
  kind?: JobKind
  project?: string
  step?: string | null
  step_index?: number
  steps?: string[]
  /** 目前步驟的進度 0~1 */
  progress?: number
  error?: string | null
  /** 失敗的步驟索引 */
  failed_step?: number | null
  /** 輸出類工作完成後的成品相對路徑 */
  output?: string | null
}

export type ProjectStatus = 'ready' | 'running' | 'failed'

export interface ProjectListItem {
  name: string
  status: ProjectStatus
  error: string | null
  /** running：目前步驟名稱與進度 */
  step?: string | null
  progress?: number
  /** failed：失敗步驟名稱 */
  failed_step?: string
  /** ready 但最近一次重新扒譜失敗 */
  reimport_error?: string
  reimport_failed_step?: string
  /** 以下由 score.json 與 versions/ 取得，讀不到就沒有這個欄位 */
  bpm?: number
  /** 小節數 */
  bars?: number
  /** 歌曲長度（秒） */
  duration?: number
  /** 編輯版本數（不含 AI 譜與舊 AI 譜） */
  versions?: number
  /** score.json 與 versions/*.json 最新的修改時間（本機時間 ISO，無時區） */
  updated?: string
}

export type AudioSource = 'drums' | 'mix' | 'max' | 'hybrid'

export interface NewProjectBody {
  source: string
  name: string
  start?: number
  dur?: number
  audio?: AudioSource | null
}

export interface PreviewCursor {
  dx: number
  w: number
  y0: number
  y1: number
}

export interface PreviewMeasure {
  x0: number
  x1: number
  /** 小節編號（0 起算） */
  bar: number
  t0: number
}

export interface PreviewLine {
  /** base64 PNG（不含 data: 前綴） */
  png: string
  t0: number
  t1: number
  /** [時間秒, 游標 x 像素]，依時間排序 */
  evs: [number, number][]
  width: number
  height: number
  cursor: PreviewCursor
  measures: PreviewMeasure[]
  /** 每一行的 [起, 止] 秒 */
  lines: [number, number][]
}

export interface PreviewBody {
  score: Score
  line: number
  simile: boolean
}

export interface RenderBody {
  crop_y: number
  simile: boolean
}

export interface ExportSheetBody {
  version: string
  format: 'pdf' | 'png'
  simile: boolean
}

export interface ExportSheetResult {
  files: string[]
  pages: number
  folder: string
}

export interface VersionCreated {
  id: string
  name: string
  kind: 'edited'
  source: string
  created: string
}
