import { create } from 'zustand'
import type { Act, Bar, Score } from '@/lib/types'
import { barContent, type BarContent } from './lib/bar'
import { emptyHistory, record, redoStep, undoStep, type History } from './lib/history'

export type PlaySource = 'mix' | 'drums'
/** 只聽音源 / 音源 + 我寫的譜 / 只聽我寫的譜 */
export type PlayMode = 'src' | 'both' | 'synth'

export interface LoadedScore {
  project: string
  version: string
}

export interface LoadPayload {
  project: string
  version: string
  score: Score
  act: Act
  media: string[]
}

interface EditorState {
  /** 目前記憶體中的鼓譜屬於哪個專案／版本；還沒載入為 null */
  loaded: LoadedScore | null
  score: Score | null
  act: Act
  media: string[]
  /** 目前小節（0 起算） */
  cur: number
  dirty: boolean
  /** 鼓譜內容版次：每次內容變動（含載入、儲存後換成伺服器版）加一。預覽快取用它判斷是否作廢 */
  rev: number
  history: History
  clip: BarContent | null

  // 試聽設定（播放中的狀態不存這裡，見 playback-engine）
  source: PlaySource
  mode: PlayMode
  loop: boolean
  playing: boolean

  /** 載入鼓譜。同專案保留目前小節（切版本），換專案回到第 0 小節。 */
  load: (p: LoadPayload) => void
  /** 清空（離開編輯器頁時） */
  reset: () => void
  setCur: (i: number) => void
  /** 修改目前小節：記錄復原點、標成有未存修改 */
  editBar: (fn: (b: Bar) => Bar) => void
  undo: () => void
  redo: () => void
  copyBar: () => void
  /** 儲存成功後換成伺服器回傳的鼓譜。儲存期間又改過（rev 不同）就保留記憶體中的版本。 */
  markSaved: (fresh: Score, revAtSave: number) => void
  /** 放棄修改、不再視為有未存修改（例如刪除版本前） */
  markClean: () => void
  setSource: (s: PlaySource) => void
  setMode: (m: PlayMode) => void
  setLoop: (b: boolean) => void
  setPlaying: (b: boolean) => void
}

function replaceBar(score: Score, i: number, bar: Bar): Score {
  const bars = [...score.bars]
  bars[i] = bar
  return { ...score, bars }
}

const initial = {
  loaded: null,
  score: null,
  act: null,
  media: [] as string[],
  cur: 0,
  dirty: false,
  rev: 0,
  history: emptyHistory,
  clip: null,
}

export const useEditorStore = create<EditorState>()((set, get) => ({
  ...initial,
  source: 'mix',
  mode: 'both',
  loop: false,
  playing: false,

  load: ({ project, version, score, act, media }) =>
    set((s) => {
      const sameProject = s.loaded?.project === project
      const cur = sameProject ? Math.max(0, Math.min(s.cur, score.bars.length - 1)) : 0
      return {
        loaded: { project, version },
        score,
        act,
        media,
        cur,
        dirty: false,
        rev: s.rev + 1,
        history: emptyHistory,
        // 沒有 drums.wav 時不能停在「只有鼓聲」
        source: media.includes('drums.wav') ? s.source : 'mix',
      }
    }),

  reset: () => set((s) => ({ ...initial, rev: s.rev + 1, playing: false })),

  setCur: (i) => set({ cur: i }),

  editBar: (fn) =>
    set((s) => {
      if (!s.score) return {}
      const bar = s.score.bars[s.cur]
      return {
        score: replaceBar(s.score, s.cur, fn(bar)),
        history: record(s.history, s.cur, bar),
        dirty: true,
        rev: s.rev + 1,
      }
    }),

  undo: () =>
    set((s) => {
      if (!s.score) return {}
      const r = undoStep(s.history, s.score.bars)
      if (!r) return {}
      return {
        score: { ...s.score, bars: r.bars },
        history: r.history,
        cur: r.index,
        dirty: true,
        rev: s.rev + 1,
      }
    }),

  redo: () =>
    set((s) => {
      if (!s.score) return {}
      const r = redoStep(s.history, s.score.bars)
      if (!r) return {}
      return {
        score: { ...s.score, bars: r.bars },
        history: r.history,
        cur: r.index,
        dirty: true,
        rev: s.rev + 1,
      }
    }),

  copyBar: () => {
    const { score, cur } = get()
    if (score) set({ clip: barContent(score.bars[cur]) })
  },

  markSaved: (fresh, revAtSave) =>
    set((s) => (s.rev === revAtSave ? { score: fresh, dirty: false, rev: s.rev + 1 } : {})),

  markClean: () => set({ dirty: false }),

  setSource: (source) => set({ source }),
  setMode: (mode) => set({ mode }),
  setLoop: (loop) => set({ loop }),
  setPlaying: (playing) => set({ playing }),
}))
