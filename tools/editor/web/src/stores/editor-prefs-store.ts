import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { clampVolume } from '@/features/editor/lib/volume'

/** 編輯器的個人偏好（存在瀏覽器 localStorage，換專案也沿用） */
interface EditorPrefs {
  /** 上方畫面裁切：0.5 置中、0 保留上方、1 保留下方 */
  cropY: number
  /** 重複小節用 % 記號 */
  simile: boolean
  /** 提前一拍開始播放 */
  preroll: boolean
  /** 播放速度 */
  rate: number
  /** 音源（原曲或鼓聲）音量 0–1 */
  srcVolume: number
  /** 合成鼓聲（我寫的譜）音量 0–1 */
  synthVolume: number
  setCropY: (v: number) => void
  setSimile: (v: boolean) => void
  setPreroll: (v: boolean) => void
  setRate: (v: number) => void
  setSrcVolume: (v: number) => void
  setSynthVolume: (v: number) => void
}

export const useEditorPrefs = create<EditorPrefs>()(
  persist(
    (set) => ({
      cropY: 0.5,
      simile: true,
      preroll: true,
      rate: 1,
      srcVolume: 1,
      synthVolume: 0.7,
      setCropY: (cropY) => set({ cropY }),
      setSimile: (simile) => set({ simile }),
      setPreroll: (preroll) => set({ preroll }),
      setRate: (rate) => set({ rate }),
      setSrcVolume: (v) => set({ srcVolume: clampVolume(v, 1) }),
      setSynthVolume: (v) => set({ synthVolume: clampVolume(v, 0.7) }),
    }),
    { name: 'dce.editor-prefs' }
  )
)
