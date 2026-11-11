import { createContext, useContext, type RefObject } from 'react'
import type { VersionInfo } from '@/lib/types'
import type { EditorActions } from './use-editor-actions'
import type { Playback } from './use-playback'

export interface EditorContextValue {
  project: string
  /** 目前載入的版本 id */
  version: string
  versions: VersionInfo[]
  /** 目前這份鼓譜是不是唯讀（AI 譜、舊 AI 譜） */
  readOnly: boolean
  actions: EditorActions
  playback: Playback
  refs: {
    video: RefObject<HTMLVideoElement | null>
    audio: RefObject<HTMLAudioElement | null>
    grid: RefObject<HTMLDivElement | null>
    playhead: RefObject<HTMLDivElement | null>
  }
}

export const EditorContext = createContext<EditorContextValue | null>(null)

export function useEditor(): EditorContextValue {
  const v = useContext(EditorContext)
  if (!v) throw new Error('useEditor 必須在編輯器頁面內使用')
  return v
}
