/**
 * WebAudio 合成鼓聲（音色參數原樣移植自舊版 index.html）。
 * 用法：
 *   const synth = new DrumSynth()
 *   await synth.resume()            // 必須在使用者操作（點擊/按鍵）之後
 *   synth.hit('SD', synth.currentTime + 0.03)
 *   synth.stopAll()                 // 停止所有已排程、尚未播完的聲音
 */
export class DrumSynth {
  private ctx: AudioContext | null = null
  private master: GainNode | null = null
  private noise: AudioBuffer | null = null
  private scheduled: AudioScheduledSourceNode[] = []

  private audio(): AudioContext {
    if (!this.ctx) {
      const ctx = new AudioContext()
      const master = ctx.createGain()
      master.gain.value = 0.7
      master.connect(ctx.destination)
      const noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate)
      const d = noise.getChannelData(0)
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1
      this.ctx = ctx
      this.master = master
      this.noise = noise
    }
    return this.ctx
  }

  /** AudioContext 目前時間（秒）；還沒建立時為 0。排程用：`when = synth.currentTime + 延遲`。 */
  get currentTime(): number {
    return this.ctx?.currentTime ?? 0
  }

  /** 建立（必要時）並啟動 AudioContext。 */
  async resume(): Promise<void> {
    await this.audio().resume()
  }

  /** 停止所有已排程的聲音。 */
  stopAll(): void {
    for (const s of this.scheduled) {
      try {
        s.stop()
      } catch {
        // 已經停了
      }
    }
    this.scheduled = []
  }

  private env(g: GainNode, when: number, peak: number, decay: number) {
    g.gain.setValueAtTime(peak, when)
    g.gain.exponentialRampToValueAtTime(0.001, when + decay)
  }

  private noiseHit(
    when: number,
    type: BiquadFilterType,
    freq: number,
    peak: number,
    decay: number,
    q = 0.8
  ) {
    const ctx = this.audio()
    const s = ctx.createBufferSource()
    s.buffer = this.noise
    const f = ctx.createBiquadFilter()
    f.type = type
    f.frequency.value = freq
    f.Q.value = q
    const g = ctx.createGain()
    this.env(g, when, peak, decay)
    s.connect(f).connect(g).connect(this.master!)
    s.start(when)
    s.stop(when + decay + 0.05)
    this.scheduled.push(s)
  }

  private toneHit(
    when: number,
    f0: number,
    f1: number,
    peak: number,
    decay: number,
    type: OscillatorType = 'sine'
  ) {
    const ctx = this.audio()
    const o = ctx.createOscillator()
    o.type = type
    o.frequency.setValueAtTime(f0, when)
    o.frequency.exponentialRampToValueAtTime(f1, when + decay * 0.6)
    const g = ctx.createGain()
    this.env(g, when, peak, decay)
    o.connect(g).connect(this.master!)
    o.start(when)
    o.stop(when + decay + 0.05)
    this.scheduled.push(o)
  }

  /** 在 AudioContext 時間 `when`（秒）發出樂器 `name`（樂器代號）的聲音。未知代號忽略。 */
  hit(name: string, when: number): void {
    switch (name) {
      case 'BD':
        this.toneHit(when, 140, 45, 1.0, 0.28)
        break
      case 'SD':
        this.noiseHit(when, 'bandpass', 1900, 0.9, 0.17)
        this.toneHit(when, 200, 160, 0.35, 0.09, 'triangle')
        break
      case 'XS':
        this.toneHit(when, 1150, 950, 0.35, 0.05, 'triangle')
        this.noiseHit(when, 'highpass', 3000, 0.2, 0.03)
        break
      case 'HH':
        this.noiseHit(when, 'highpass', 7500, 0.4, 0.05)
        break
      case 'HO':
        this.noiseHit(when, 'highpass', 6500, 0.35, 0.38)
        break
      case 'HF':
        this.noiseHit(when, 'highpass', 6000, 0.25, 0.04)
        break
      case 'CR':
        this.noiseHit(when, 'highpass', 4200, 0.55, 1.3, 0.5)
        break
      case 'RD':
        this.noiseHit(when, 'bandpass', 6500, 0.3, 0.55)
        this.toneHit(when, 3100, 3000, 0.08, 0.5)
        break
      case 'TH':
        this.toneHit(when, 260, 180, 0.8, 0.3)
        break
      case 'TM':
        this.toneHit(when, 180, 125, 0.8, 0.33)
        break
      case 'TF':
        this.toneHit(when, 115, 80, 0.9, 0.4)
        break
    }
  }
}

/** 工廠寫法（等同 new DrumSynth()） */
export const createDrumSynth = () => new DrumSynth()
