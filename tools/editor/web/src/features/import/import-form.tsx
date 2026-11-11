import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AudioLines, ChevronDown, Info, Loader2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { JOB_KEY, JOB_KIND_LABEL, useJob } from '@/hooks/use-job'
import * as api from '@/lib/api'
import type { AudioSource } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useProjectList } from '@/features/projects/use-project-list'
import { sanitizeProjectName } from './lib/sanitize-name'
import {
  NAME_MAX,
  checkProjectName,
  checkSeconds,
  checkSource,
  normalizeSource,
} from './lib/validate'
import { useImportUi } from './store'

const DEFAULT_AUDIO = 'default'
const AUDIO_OPTIONS: { value: string; label: string; hint: string }[] = [
  {
    value: DEFAULT_AUDIO,
    label: '自動（建議）',
    hint: '開合 hi-hat 看完整混音（分離會削弱輕的 hi-hat），其他鼓看分離出的鼓聲。大多數歌曲選這個就好。',
  },
  { value: 'drums', label: '只用分離出的鼓聲', hint: '雜音最少，但輕的 hi-hat 容易漏掉。' },
  { value: 'mix', label: '只用完整混音', hint: '不受分離品質影響，但其他樂器可能被誤判成鼓聲。' },
  { value: 'max', label: '兩者逐幀取較大值', hint: '最敏感，不想漏音符時用，可能多出一些多餘的音符。' },
]

/** 後端錯誤依內容歸到對應欄位；歸不到的放在按鈕旁 */
function routeError(e: unknown): { field: 'source' | 'name' | 'form'; message: string } {
  const message = (e as Error).message
  const status = (e as { status?: number }).status
  const busy = (e as { busy?: boolean }).busy
  if (busy) return { field: 'form', message }
  if (status === 409 || /名稱/.test(message)) return { field: 'name', message }
  if (/網址|mp4|路徑/.test(message)) return { field: 'source', message }
  return { field: 'form', message }
}

function FieldError({ id, children }: { id: string; children?: string }) {
  if (!children) return null
  return (
    <p id={id} role="alert" className="text-destructive text-sm">
      {children}
    </p>
  )
}

function Hint({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <p id={id} className="text-muted-foreground text-xs">
      {children}
    </p>
  )
}

export function ImportForm() {
  const qc = useQueryClient()
  const { job, busy } = useJob()
  const { data: projects } = useProjectList()
  const resetUi = useImportUi((s) => s.reset)

  const [source, setSource] = useState('')
  const [sourceTouched, setSourceTouched] = useState(false)
  const [name, setName] = useState('')
  const [nameEdited, setNameEdited] = useState(false)
  const [start, setStart] = useState('')
  const [dur, setDur] = useState('')
  const [audio, setAudio] = useState(DEFAULT_AUDIO)
  const [advOpen, setAdvOpen] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [titleError, setTitleError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [refetchTick, setRefetchTick] = useState(0)
  const [serverError, setServerError] = useState<{ field: 'source' | 'name' | 'form'; message: string }>()

  const sourceRef = useRef<HTMLInputElement>(null)
  const titleSeq = useRef(0)
  const lastFetched = useRef('')
  const nameEditedRef = useRef(false)

  const normalized = normalizeSource(source)
  const sourceCheck = checkSource(source)
  const existing = (projects ?? []).map((p) => p.name)
  const nameCheck = checkProjectName(name, existing)
  const startError = checkSeconds(start)
  const durError = checkSeconds(dur)
  const validSource = sourceCheck.kind === 'url' || sourceCheck.kind === 'file'

  // 貼上（或輸入）合法來源後稍等一下自動取影片標題當專案名稱
  useEffect(() => {
    if (!validSource || normalized === lastFetched.current) return
    const timer = setTimeout(() => {
      lastFetched.current = normalized
      const seq = ++titleSeq.current
      setFetching(true)
      setTitleError('')
      api
        .projectTitle(normalized)
        .then((d) => {
          if (seq !== titleSeq.current) return
          if (!nameEditedRef.current) setName(sanitizeProjectName(d.title))
        })
        .catch((e: unknown) => {
          if (seq !== titleSeq.current) return
          const err = e as Error & { status?: number }
          setTitleError(
            sourceCheck.kind === 'file' && err.status === 400
              ? '找不到這個檔案，請確認路徑正確（可以在檔案總管對檔案按右鍵選「複製為路徑」）。'
              : `${err.message} 你仍然可以自己輸入專案名稱。`
          )
        })
        .finally(() => {
          if (seq === titleSeq.current) setFetching(false)
        })
    }, 500)
    return () => clearTimeout(timer)
  }, [normalized, validSource, sourceCheck.kind, refetchTick])

  function clearSource() {
    setSource('')
    setSourceTouched(false)
    setTitleError('')
    setServerError(undefined)
    setFetching(false)
    titleSeq.current++
    lastFetched.current = ''
    if (!nameEditedRef.current) setName('')
    sourceRef.current?.focus()
  }

  function refetchTitle() {
    lastFetched.current = ''
    nameEditedRef.current = false
    setNameEdited(false)
    setRefetchTick((n) => n + 1)
  }

  const otherJob =
    busy && job?.kind
      ? `目前正在${JOB_KIND_LABEL[job.kind].running}${job.project ? `「${job.project}」` : ''}`
      : ''

  // 按鈕停用的第一個原因（同時當作說明文字）
  let blockReason = ''
  if (busy) blockReason = '目前的工作結束後才能開始。'
  else if (sourceCheck.kind === 'empty') blockReason = '先貼上影片網址或 mp4 路徑。'
  else if (sourceCheck.kind === 'invalid') blockReason = sourceTouched ? '來源格式不正確，請見上方說明。' : (sourceCheck.message ?? '')
  else if (fetching && !name.trim()) blockReason = '正在取得影片標題…'
  else if (nameCheck.kind !== 'ok') blockReason = nameCheck.kind === 'empty' ? '請替專案取個名稱。' : '專案名稱需要修正，請見上方說明。'
  else if (startError) blockReason = '開始秒數需要修正。'
  else if (durError) blockReason = '長度需要修正。'

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault()
    if (blockReason || submitting) return
    setServerError(undefined)
    setSubmitting(true)
    resetUi()
    try {
      await api.projectNew({
        source: normalized,
        name: name.trim(),
        start: Number(start) || 0,
        dur: Number(dur) || 0,
        audio: audio === DEFAULT_AUDIO ? null : (audio as AudioSource),
      })
      // 等工作狀態更新後，頁面會自動換成進度畫面
      await qc.refetchQueries({ queryKey: JOB_KEY })
      void qc.invalidateQueries({ queryKey: ['project_list'] })
    } catch (e) {
      setServerError(routeError(e))
      void qc.invalidateQueries({ queryKey: JOB_KEY })
    } finally {
      setSubmitting(false)
    }
  }

  const showSourceError =
    serverError?.field === 'source'
      ? serverError.message
      : sourceCheck.kind === 'invalid' && sourceTouched
        ? sourceCheck.message
        : titleError
  const showNameError =
    serverError?.field === 'name'
      ? serverError.message
      : nameCheck.kind === 'invalid' || nameCheck.kind === 'duplicate'
        ? nameCheck.message
        : nameCheck.kind === 'empty' && nameEdited
          ? nameCheck.message
          : undefined
  const audioHint = AUDIO_OPTIONS.find((o) => o.value === audio)?.hint

  return (
    <Card>
      <CardHeader>
        <CardTitle>把歌曲扒成鼓譜</CardTitle>
        <CardDescription>貼上 YouTube 網址或本機 mp4 檔案路徑，其餘交給我們。</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="grid gap-5" noValidate>
          {busy && (
            <div
              role="status"
              className="bg-muted text-muted-foreground flex items-start gap-2 rounded-md px-3 py-2 text-sm"
            >
              <Info className="mt-0.5 size-4 shrink-0" />
              <span>
                同時只能跑一個工作。{otherJob}，完成後才能開始扒譜；你可以先把網址貼好。
              </span>
            </div>
          )}

          <div className="grid gap-1.5">
            <Label htmlFor="src">YouTube 網址或本機 mp4 路徑</Label>
            <div className="relative">
              <Input
                id="src"
                ref={sourceRef}
                autoFocus
                value={source}
                onChange={(e) => {
                  setSource(e.target.value)
                  setServerError(undefined)
                }}
                onBlur={() => setSourceTouched(true)}
                placeholder="https://www.youtube.com/watch?v=… 或 C:\影片\練習.mp4"
                autoComplete="off"
                spellCheck={false}
                className={cn(source && 'pe-9!')}
                aria-invalid={!!showSourceError}
                aria-describedby="src-hint src-err"
              />
              {source && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute end-0.5 top-1/2 size-8 -translate-y-1/2"
                  onClick={clearSource}
                  aria-label="清除來源"
                >
                  <X />
                </Button>
              )}
            </div>
            <FieldError id="src-err">{showSourceError}</FieldError>
            {!showSourceError && (
              <Hint id="src-hint">
                本機檔案可在檔案總管對檔案按右鍵選「複製為路徑」再貼上。
              </Hint>
            )}
          </div>

          <div className="grid gap-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="name">專案名稱</Label>
              {validSource && titleError && !fetching && (
                <button
                  type="button"
                  onClick={refetchTitle}
                  className="text-primary rounded text-xs underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:outline-none"
                >
                  重新取得標題
                </button>
              )}
            </div>
            <div className="relative">
              <Input
                id="name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value)
                  nameEditedRef.current = true
                  setNameEdited(true)
                  setServerError(undefined)
                }}
                placeholder={fetching ? '正在取得影片標題…' : '例如：夜に駆ける - YOASOBI'}
                autoComplete="off"
                className={cn(fetching && 'pe-9!')}
                aria-invalid={!!showNameError}
                aria-describedby="name-hint name-err"
              />
              {fetching && (
                <Loader2
                  aria-label="正在取得影片標題"
                  className="text-muted-foreground absolute end-3 top-1/2 size-4 -translate-y-1/2 animate-spin"
                />
              )}
            </div>
            <FieldError id="name-err">{showNameError}</FieldError>
            {!showNameError && (
              <Hint id="name-hint">
                預設用影片標題，可以自己改。{name.trim().length > 60 && `（${name.trim().length} / ${NAME_MAX} 字）`}
              </Hint>
            )}
          </div>

          <Collapsible open={advOpen} onOpenChange={setAdvOpen}>
            <CollapsibleTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-muted-foreground -ms-2"
              >
                <ChevronDown
                  className={cn('transition-transform', advOpen && 'rotate-180')}
                />
                進階選項
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 grid gap-4 sm:grid-cols-2">
              <div className="grid content-start gap-1.5">
                <Label htmlFor="start">開始秒數</Label>
                <Input
                  id="start"
                  type="number"
                  min={0}
                  step={0.1}
                  placeholder="0"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  aria-invalid={!!startError}
                  aria-describedby="start-hint"
                />
                {startError ? (
                  <FieldError id="start-hint">{startError}</FieldError>
                ) : (
                  <Hint id="start-hint">跳過片頭：從影片的第幾秒開始扒。</Hint>
                )}
              </div>
              <div className="grid content-start gap-1.5">
                <Label htmlFor="dur">長度（秒）</Label>
                <Input
                  id="dur"
                  type="number"
                  min={0}
                  step={0.1}
                  placeholder="到最後"
                  value={dur}
                  onChange={(e) => setDur(e.target.value)}
                  aria-invalid={!!durError}
                  aria-describedby="dur-hint"
                />
                {durError ? (
                  <FieldError id="dur-hint">{durError}</FieldError>
                ) : (
                  <Hint id="dur-hint">只扒這麼長；空白代表扒到影片最後。</Hint>
                )}
              </div>
              <div className="grid content-start gap-1.5 sm:col-span-2">
                <Label htmlFor="audio">扒譜音源</Label>
                <Select value={audio} onValueChange={setAudio}>
                  <SelectTrigger id="audio" className="w-full" aria-describedby="audio-hint">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {AUDIO_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Hint id="audio-hint">{audioHint}</Hint>
              </div>
            </CollapsibleContent>
          </Collapsible>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Button type="submit" disabled={!!blockReason || submitting}>
              {submitting ? <Loader2 className="animate-spin" /> : <AudioLines />}
              開始扒譜
            </Button>
            {blockReason && !submitting && (
              <span className="text-muted-foreground min-w-0 flex-1 text-sm" id="submit-reason">
                {blockReason}
              </span>
            )}
          </div>
          {serverError?.field === 'form' && (
            <p role="alert" className="text-destructive text-sm whitespace-pre-wrap">
              {serverError.message}
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
