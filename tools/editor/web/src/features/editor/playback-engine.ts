import type { Bar } from '@/lib/types'
import { useEditorPrefs } from '@/stores/editor-prefs-store'
import { tickTime } from './lib/bar'
import { barStartTime, playheadPosition } from './lib/playhead'
import { createDrumSynth } from './lib/synth'
import { useEditorStore } from './store'

/** 一小節播完後再多等多久（秒）才算結束，避免卡在最後一個音 */
const END_SLACK = 0.02
/** 排程合成鼓聲時，比媒體時間早到的音（已經過去）的容許誤差（秒） */
const PAST_SLACK = 0.01
/** 合成鼓聲比媒體多延後一點，給 AudioContext 排程的餘裕（秒） */
const SCHEDULE_LEAD = 0.03

export interface EngineDeps {
  video: () => HTMLVideoElement | null
  audio: () => HTMLAudioElement | null
  grid: () => HTMLElement | null
  playhead: () => HTMLElement | null
  onError: (message: string) => void
}

/**
 * 試聽引擎：負責「播放這一小節」——同步媒體（原曲影片或鼓聲 wav）與合成鼓聲、
 * 小節結束時循環或停止、移動方格上的紅色播放頭。
 *
 * 播放頭與「目前拍」直接改 DOM（style / data-current），不走 React state；
 * 只有 playing 會寫進 store。
 *
 * 同步方式：播放開始後，第一個「實際前進」的畫格建立 (AudioContext 時間, 媒體時間) 的對應，
 * 再用這個對應把這小節的合成鼓聲排進 AudioContext。
 */
export class PlaybackEngine {
  playing = false
  private sync: { ctx: number; media: number } | null = null
  private raf = 0
  private lastBeat = -1
  private readonly synth = createDrumSynth()

  constructor(private readonly deps: EngineDeps) {}

  private state() {
    const s = useEditorStore.getState()
    const bar = s.score?.bars[s.cur]
    return { bar, source: s.source, mode: s.mode, loop: s.loop, ...useEditorPrefs.getState() }
  }

  private player(): HTMLMediaElement | null {
    const { source } = this.state()
    const audio = this.deps.audio()
    if (source === 'drums' && audio?.getAttribute('src')) return audio
    return this.deps.video()
  }

  /** 從目前小節的起點（提前一拍或 0.05 秒）開始播放。已在播放就重新開始（改音源、速度時用）。 */
  async play(): Promise<void> {
    const video = this.deps.video()
    const audio = this.deps.audio()
    const p = this.player()
    const { bar, rate, mode, preroll } = this.state()
    if (!video || !audio || !p || !bar) return

    await this.synth.resume()
    this.synth.stopAll()
    for (const m of [video, audio]) if (m !== p) m.pause()
    p.playbackRate = rate
    p.preservesPitch = true
    p.muted = mode === 'synth'
    p.currentTime = barStartTime(bar, preroll)
    if (p === audio && video.getAttribute('src')) {
      // 音源是鼓聲 wav 時，影片靜音同步跑，畫面才對得上
      video.muted = true
      video.currentTime = p.currentTime
      video.playbackRate = rate
      video.play().catch(() => {})
    }
    this.playing = true
    this.sync = null
    useEditorStore.getState().setPlaying(true)
    try {
      await p.play()
    } catch (e) {
      this.stop()
      this.deps.onError(`無法播放：${(e as Error).message}`)
      return
    }
    if (!this.playing) return // 等待期間已經被停止
    cancelAnimationFrame(this.raf)
    this.raf = requestAnimationFrame(this.tick)
  }

  /** 排程這一小節尚未發生的合成鼓聲 */
  private scheduleSynth(): void {
    const { bar, mode, rate } = this.state()
    if (mode === 'src' || !bar || !this.sync) return
    for (const e of bar.events) {
      const t = tickTime(bar, e.tick)
      if (t < this.sync.media - PAST_SLACK) continue
      const when = this.sync.ctx + (t - this.sync.media) / rate + SCHEDULE_LEAD
      for (const n of e.notes) this.synth.hit(n, when)
    }
  }

  private tick = (): void => {
    if (!this.playing) return
    const p = this.player()
    const { bar, loop, preroll } = this.state()
    if (!p || !bar) return
    const t = p.currentTime
    if (!this.sync && !p.paused && !p.seeking && p.readyState >= 3 && t > 0) {
      this.sync = { ctx: this.synth.currentTime, media: t }
      this.scheduleSynth()
    }
    this.movePlayhead(bar, t)
    if (t >= bar.t1 + END_SLACK) {
      if (loop) {
        this.synth.stopAll()
        p.currentTime = barStartTime(bar, preroll)
        this.sync = null
        const video = this.deps.video()
        if (p === this.deps.audio() && video?.getAttribute('src')) video.currentTime = p.currentTime
      } else {
        this.stop()
        return
      }
    }
    this.raf = requestAnimationFrame(this.tick)
  }

  /** 紅色播放頭與目前拍：依實際拍點分段，直接改 DOM */
  private movePlayhead(bar: Bar, t: number) {
    const grid = this.deps.grid()
    const ph = this.deps.playhead()
    if (!grid || !ph) return
    const beatEls = grid.querySelectorAll<HTMLElement>('[data-beat-marker]')
    const pos = playheadPosition(bar, t)
    if (!pos || pos.beat >= beatEls.length) {
      ph.style.display = 'none'
      this.markBeat(grid, -1)
      return
    }
    const gr = grid.getBoundingClientRect()
    const br = beatEls[pos.beat].getBoundingClientRect()
    ph.style.left = `${br.left - gr.left + pos.frac * br.width}px`
    ph.style.display = 'block'
    this.markBeat(grid, pos.beat)
  }

  private markBeat(grid: HTMLElement, beat: number) {
    if (beat === this.lastBeat) return
    this.lastBeat = beat
    grid.querySelectorAll<HTMLElement>('[data-beat-head]').forEach((el, i) => {
      el.dataset.current = String(i === beat)
    })
  }

  /** 停止播放、停掉合成鼓聲、藏起播放頭。 */
  stop(): void {
    this.playing = false
    cancelAnimationFrame(this.raf)
    this.synth.stopAll()
    this.deps.video()?.pause()
    this.deps.audio()?.pause()
    const ph = this.deps.playhead()
    if (ph) ph.style.display = 'none'
    const grid = this.deps.grid()
    if (grid) this.markBeat(grid, -1)
    if (useEditorStore.getState().playing) useEditorStore.getState().setPlaying(false)
  }

  /** 把影片時間設成目前小節的 t0（預覽跟著影片時間，所以跳小節就是把影片跳過去）。 */
  seekToBar(): void {
    const video = this.deps.video()
    const { bar } = this.state()
    if (bar && video?.getAttribute('src') && video.readyState > 0) video.currentTime = bar.t0
  }

  dispose(): void {
    this.stop()
  }
}
