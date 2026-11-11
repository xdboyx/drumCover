import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { toast } from 'sonner'
import { useEditorPrefs } from '@/stores/editor-prefs-store'
import { barIndexAt } from './lib/bar'
import { PlaybackEngine } from './playback-engine'
import { useEditorStore } from './store'

export interface PlaybackRefs {
  video: RefObject<HTMLVideoElement | null>
  audio: RefObject<HTMLAudioElement | null>
  grid: RefObject<HTMLDivElement | null>
  playhead: RefObject<HTMLDivElement | null>
}

export interface Playback {
  play: () => void
  stop: () => void
  toggle: () => void
  /** 跳到第 i 小節：停止播放、影片時間設成小節起點；原本在播且循環開著就繼續播 */
  go: (i: number) => void
  /** 影片 metadata 載入完成：把影片時間設到目前小節（播放中不動） */
  onVideoLoaded: () => void
  /** 使用者直接用影片控制列播放或拖曳時，讓「目前小節」跟著影片時間走 */
  onVideoTime: () => void
}

/** 試聽：把 PlaybackEngine 接到 React（元件卸載時停止、播放中改音源/速度/模式時重新開始）。 */
export function usePlayback(refs: PlaybackRefs): Playback {
  const refsRef = useRef(refs)
  useEffect(() => {
    refsRef.current = refs
  })
  const [engine] = useState(
    () =>
      new PlaybackEngine({
        video: () => refsRef.current.video.current,
        audio: () => refsRef.current.audio.current,
        grid: () => refsRef.current.grid.current,
        playhead: () => refsRef.current.playhead.current,
        onError: (m) => toast.error(m),
      })
  )

  useEffect(() => () => engine.dispose(), [engine])

  // 播放中改音源／速度／模式：照新設定重新開始
  const source = useEditorStore((s) => s.source)
  const mode = useEditorStore((s) => s.mode)
  const rate = useEditorPrefs((s) => s.rate)
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    if (engine.playing) void engine.play()
  }, [engine, source, mode, rate])

  const play = useCallback(() => void engine.play(), [engine])
  const stop = useCallback(() => engine.stop(), [engine])
  const toggle = useCallback(() => (engine.playing ? engine.stop() : void engine.play()), [engine])

  const go = useCallback(
    (i: number) => {
      const s = useEditorStore.getState()
      if (!s.score || i < 0 || i >= s.score.bars.length) return
      const wasPlaying = engine.playing
      engine.stop()
      s.setCur(i)
      engine.seekToBar()
      if (wasPlaying && useEditorStore.getState().loop) void engine.play()
    },
    [engine]
  )

  const onVideoLoaded = useCallback(() => {
    if (!engine.playing) engine.seekToBar()
  }, [engine])

  const onVideoTime = useCallback(() => {
    if (engine.playing || performance.now() - engine.stoppedAt < 500) return // 「播放這一小節」自己管小節
    const video = refsRef.current.video.current
    const s = useEditorStore.getState()
    if (!video || !s.score) return
    const i = barIndexAt(s.score.bars, video.currentTime)
    if (i !== s.cur) s.setCur(i)
  }, [engine])

  return { play, stop, toggle, go, onVideoLoaded, onVideoTime }
}
