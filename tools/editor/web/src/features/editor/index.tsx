import { useMemo, useRef, type ReactNode } from 'react'
import { Link, useBlocker } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useOnJobFinished } from '@/hooks/use-job'
import { cn } from '@/lib/utils'
import { BarToolbar } from './bar-toolbar'
import { EditorContext, type EditorContextValue } from './context'
import { EditorToolbar } from './editor-toolbar'
import { ExportPanel } from './export-panel'
import { HelpPanel } from './help-panel'
import { isReadOnlyVersion, warningText } from './lib/version'
import { NoteGrid } from './note-grid'
import { Overview } from './overview'
import { PlaybackPanel } from './playback-panel'
import { ScorePreview } from './score-preview'
import { useEditorStore } from './store'
import { fetchIntoStore, useEditorActions, versionsKey } from './use-editor-actions'
import { useEditorData } from './use-editor-data'
import { usePlayback } from './use-playback'
import { usePrompts } from './use-prompts'
import { useShortcuts } from './use-shortcuts'

function Message({
  title,
  description,
  children,
}: {
  title: string
  description?: ReactNode
  children?: ReactNode
}) {
  return (
    <>
      <Header title="編輯器" />
      <Main>
        <Card className="mx-auto max-w-xl">
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {children}
            <Button asChild variant="outline" size="sm">
              <Link to="/">
                <ArrowLeft /> 回到專案清單
              </Link>
            </Button>
          </CardContent>
        </Card>
      </Main>
    </>
  )
}

/** 鼓譜編輯器頁面：只負責組裝；狀態在 store.ts，播放與預覽在各自的 hook。 */
export function EditorPage({ project, version }: { project?: string; version: string }) {
  const qc = useQueryClient()
  const { prompts, element: promptElement } = usePrompts()
  const data = useEditorData(project, version)

  const refs = {
    video: useRef<HTMLVideoElement>(null),
    audio: useRef<HTMLAudioElement>(null),
    grid: useRef<HTMLDivElement>(null),
    playhead: useRef<HTMLDivElement>(null),
  }
  const playback = usePlayback(refs)
  const actions = useEditorActions(project ?? '', prompts, playback)
  useShortcuts(actions, playback)

  // 站內導覽（切版本、切專案、回專案清單）遇到未存修改就詢問；關分頁用 beforeunload
  useBlocker({
    shouldBlockFn: async () => {
      if (!useEditorStore.getState().dirty) return false
      return !(await actions.confirmLeave())
    },
    enableBeforeUnload: () => useEditorStore.getState().dirty,
  })

  // 重新扒譜完成：沒有未存修改就重新載入目前的鼓譜，有就只更新版本清單
  useOnJobFinished(
    'reimport',
    (job) => {
      if (job.state !== 'done') {
        toast.error('重新扒譜失敗')
        return
      }
      toast.success('重新扒譜完成')
      const s = useEditorStore.getState()
      const refresh = () => qc.invalidateQueries({ queryKey: versionsKey(project ?? '') })
      if (s.dirty || !s.loaded) {
        void refresh()
      } else {
        fetchIntoStore(s.loaded.project, s.loaded.version)
          .then(refresh)
          .catch((e: Error) => toast.error(`重新載入失敗：${e.message}`))
      }
    },
    project
  )

  const loadedVersion = data.loaded?.version ?? version
  const readOnly = isReadOnlyVersion(loadedVersion, data.versions)
  const ctx = useMemo<EditorContextValue | null>(
    () =>
      project
        ? {
            project,
            version: loadedVersion,
            versions: data.versions,
            readOnly,
            actions,
            playback,
            refs,
          }
        : null,
    // actions / playback 每次 render 都是新物件，但內容只依賴 store，這裡以版本與清單為準
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [project, loadedVersion, data.versions, readOnly, playback]
  )

  if (data.status === 'no-project') {
    return (
      <Message title="尚未選擇專案" description="請先從專案清單選一個專案，再開啟編輯器。" />
    )
  }
  if (data.status === 'error') {
    return (
      <Message
        title={`無法開啟「${project}」`}
        description={data.error ?? '載入失敗'}
      >
        {version !== 'ai' && (
          <Button asChild size="sm">
            <Link to="/editor" search={{ p: project }}>
              改開 AI 譜
            </Link>
          </Button>
        )}
      </Message>
    )
  }
  if (data.status === 'loading' || !ctx) {
    return (
      <>
        <Header title={project} />
        <Main className="text-muted-foreground flex items-center justify-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" /> 載入鼓譜中…
        </Main>
      </>
    )
  }

  const current = data.versions.find((v) => v.id === loadedVersion)
  const switching = loadedVersion !== version

  return (
    <EditorContext.Provider value={ctx}>
      <Header title={project}>
        <EditorToolbar />
      </Header>
      <Main className={cn('grid content-start gap-3', switching && 'pointer-events-none opacity-70')}>
        {current?.warning && (
          <div
            role="alert"
            className="border-warning/50 bg-warning/10 text-foreground flex items-start gap-2 rounded-lg border px-3 py-2 text-sm"
          >
            <AlertTriangle className="text-warning mt-0.5 size-4 shrink-0" />
            <span>{warningText(current.warning)}</span>
          </div>
        )}
        <Overview />
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_380px] 2xl:grid-cols-[minmax(0,1fr)_420px] xl:items-start">
          <section className="bg-card grid min-w-0 gap-3 rounded-xl border p-3">
            <BarToolbar />
            <ScorePreview />
            <NoteGrid />
          </section>
          <aside className="grid gap-3 xl:sticky xl:top-[4.5rem]">
            <PlaybackPanel />
            <ExportPanel />
          </aside>
        </div>
        <HelpPanel />
      </Main>
      {promptElement}
    </EditorContext.Provider>
  )
}
