import type {
  Bar,
  ExportSheetBody,
  ExportSheetResult,
  JobStatus,
  NewProjectBody,
  PreviewBody,
  PreviewLine,
  ProjectListItem,
  RenderBody,
  Score,
  ScoreResponse,
  VersionCreated,
  VersionInfo,
} from './types'

/** 伺服器回傳的錯誤（取回應的 error 欄位）；忙碌時 busy 為 true 並附上目前的工作狀態 */
export class ApiError extends Error {
  status: number
  busy: boolean
  job?: JobStatus
  constructor(message: string, status: number, extra?: { busy?: boolean; job?: JobStatus }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.busy = extra?.busy ?? false
    this.job = extra?.job
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError('連不到伺服器，請確認編輯器伺服器還在執行', 0)
  }
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    // 非 JSON 回應
  }
  if (!res.ok) {
    const d = (data ?? {}) as { error?: string; busy?: boolean; job?: JobStatus }
    throw new ApiError(d.error || res.statusText || `HTTP ${res.status}`, res.status, d)
  }
  return data as T
}

const get = <T>(path: string) => request<T>(path)
const post = <T>(path: string, body: unknown = {}) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

const q = encodeURIComponent

// ---------------------------------------------------------------- 專案
export const projectList = () => get<ProjectListItem[]>('/api/project_list')
export const projectTitle = (source: string) =>
  get<{ title: string }>(`/api/project_title?source=${q(source)}`)
export const projectNew = (body: NewProjectBody) =>
  post<{ ok: true; name: string }>('/api/projects/new', body)
export const projectRetry = (p: string) =>
  post<{ ok: true; name: string }>(`/api/projects/retry?p=${q(p)}`)
export const projectReimport = (p: string) =>
  post<{ ok: true; name: string }>(`/api/projects/reimport?p=${q(p)}`)

// ---------------------------------------------------------------- 鼓譜與版本
export const getScore = (p: string, v = 'ai') =>
  get<ScoreResponse>(`/api/score?p=${q(p)}&v=${q(v)}`)
export const saveScore = (p: string, v: string, score: Score) =>
  post<{ ok: true; edited: number }>(`/api/score?p=${q(p)}&v=${q(v)}`, score)
export const getVersions = (p: string) => get<VersionInfo[]>(`/api/versions?p=${q(p)}`)
export const createVersion = (p: string, body: { name: string; source: string }) =>
  post<VersionCreated>(`/api/versions?p=${q(p)}`, body)
export const renameVersion = (p: string, v: string, name: string) =>
  post<{ id: string; name: string }>(`/api/version/rename?p=${q(p)}&v=${q(v)}`, { name })
export const deleteVersion = (p: string, v: string) =>
  post<{ ok: true }>(`/api/version/delete?p=${q(p)}&v=${q(v)}`)
export const restoreBar = (p: string, v: string, i: number) =>
  get<Bar>(`/api/restore_bar?p=${q(p)}&v=${q(v)}&i=${i}`)

// ---------------------------------------------------------------- 預覽與輸出
export const previewLine = (body: PreviewBody) => post<PreviewLine>('/api/preview_line', body)
export const render = (p: string, v: string, body: RenderBody) =>
  post<{ ok: true }>(`/api/render?p=${q(p)}&v=${q(v)}`, body)
export const exportSheet = (p: string, body: ExportSheetBody) =>
  post<ExportSheetResult>(`/api/export_sheet?p=${q(p)}`, body)
export const openExports = (p: string) => post<{ ok: true }>(`/api/open_exports?p=${q(p)}`)

// ---------------------------------------------------------------- 工作
export const job = () => get<JobStatus>('/api/job')

// ---------------------------------------------------------------- 媒體
export const mediaUrl = (p: string, file: 'video.mp4' | 'drums.wav' | 'mix.wav') =>
  `/media/${q(p)}/${file}`
