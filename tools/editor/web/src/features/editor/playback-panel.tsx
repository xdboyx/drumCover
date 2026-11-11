import type { ReactNode } from 'react'
import { Play, Repeat, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { mediaUrl } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useEditorPrefs } from '@/stores/editor-prefs-store'
import { useEditor } from './context'
import { useEditorStore, type PlayMode, type PlaySource } from './store'

/** 選完之後不要把焦點還給選單，否則 ←/→/空白/L 等快捷鍵會被選單吃掉 */
const noRefocus = (e: Event) => e.preventDefault()

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      {children}
    </div>
  )
}

/** 試聽與比對：影片（原生 controls）、播放控制、音源／速度／模式。 */
export function PlaybackPanel() {
  const { project, playback, refs } = useEditor()
  const media = useEditorStore((s) => s.media)
  const playing = useEditorStore((s) => s.playing)
  const loop = useEditorStore((s) => s.loop)
  const source = useEditorStore((s) => s.source)
  const mode = useEditorStore((s) => s.mode)
  const { rate, setRate, preroll, setPreroll } = useEditorPrefs()
  const hasVideo = media.includes('video.mp4')
  const hasDrums = media.includes('drums.wav')

  return (
    <section className="bg-card space-y-3 rounded-xl border p-3">
      <h2 className="text-muted-foreground text-xs font-semibold">試聽與比對</h2>
      <video
        ref={refs.video}
        src={hasVideo ? mediaUrl(project, 'video.mp4') : undefined}
        playsInline
        preload="auto"
        controls
        onLoadedMetadata={playback.onVideoLoaded}
        className="bg-black aspect-video w-full rounded-lg"
      />
      <audio ref={refs.audio} src={hasDrums ? mediaUrl(project, 'drums.wav') : undefined} preload="auto" />

      <div className="flex gap-2">
        <Button className="flex-1" onClick={playback.toggle} title="空白鍵">
          {playing ? <Square /> : <Play />}
          {playing ? '停止' : '播放這一小節'}
        </Button>
        <Button
          variant={loop ? 'default' : 'outline'}
          aria-pressed={loop}
          title="循環播放這一小節 (L)"
          onClick={() => useEditorStore.getState().setLoop(!loop)}
          className={cn(!loop && 'text-muted-foreground')}
        >
          <Repeat /> 循環
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Field label="音源">
          <Select value={source} onValueChange={(v) => useEditorStore.getState().setSource(v as PlaySource)}>
            <SelectTrigger size="sm" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper" onCloseAutoFocus={noRefocus}>
              <SelectItem value="mix">原曲（含畫面）</SelectItem>
              <SelectItem value="drums" disabled={!hasDrums}>
                只有鼓聲（分離後）
              </SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="速度">
          <Select value={String(rate)} onValueChange={(v) => setRate(Number(v))}>
            <SelectTrigger size="sm" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper" onCloseAutoFocus={noRefocus}>
              <SelectItem value="1">100%</SelectItem>
              <SelectItem value="0.75">75%</SelectItem>
              <SelectItem value="0.5">50%</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="聽">
          <Select value={mode} onValueChange={(v) => useEditorStore.getState().setMode(v as PlayMode)}>
            <SelectTrigger size="sm" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper" onCloseAutoFocus={noRefocus}>
              <SelectItem value="src">只聽音源</SelectItem>
              <SelectItem value="both">音源 + 我寫的譜</SelectItem>
              <SelectItem value="synth">只聽我寫的譜</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <div className="flex items-end pb-1.5">
          <Label className="gap-2 text-sm">
            <Switch checked={preroll} onCheckedChange={setPreroll} />
            提前一拍開始
          </Label>
        </div>
      </div>
      <p className="text-muted-foreground text-xs">
        比對訣竅：選「音源 + 我寫的譜」慢速循環播放，合成鼓聲跟原曲對不上的地方就是要改的地方。
      </p>
    </section>
  )
}
