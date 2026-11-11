import { useState } from 'react'
import { FileImage, FileText, FolderOpen, Loader2, Video } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { JOB_KIND_LABEL, useJob, useRefreshJob } from '@/hooks/use-job'
import * as api from '@/lib/api'
import { useEditorPrefs } from '@/stores/editor-prefs-store'
import { useEditor } from './context'
import { useEditorStore } from './store'

const BUSY_HINT = '有工作正在執行，請等它結束'
const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** 輸出：練習影片（裁切位置、% 記號）、鼓譜圖檔（PDF／PNG）、開啟輸出資料夾。 */
export function ExportPanel() {
  const { project, version, readOnly, actions } = useEditor()
  const { job, busy } = useJob()
  const refreshJob = useRefreshJob()
  const { cropY, setCropY, simile, setSimile } = useEditorPrefs()
  const [sheetState, setSheetState] = useState('')
  const [sheetBusy, setSheetBusy] = useState(false)

  /** 有未存修改且不是唯讀就先存檔。回傳 false 代表存檔失敗，不繼續輸出。 */
  async function saveFirst(): Promise<boolean> {
    if (useEditorStore.getState().dirty && !readOnly) return actions.save()
    return true
  }

  async function renderVideo() {
    try {
      if (!(await saveFirst())) return
      await api.render(project, version, { crop_y: cropY, simile })
      refreshJob()
    } catch (e) {
      toast.error(`無法輸出：${errMsg(e)}`)
    }
  }

  async function exportSheet(format: 'pdf' | 'png') {
    setSheetBusy(true)
    try {
      if (!(await saveFirst())) return
      setSheetState('輸出中…')
      const r = await api.exportSheet(project, { version, format, simile })
      setSheetState(
        `完成：exports/${r.files[0]}${r.files.length > 1 ? ` 等 ${r.files.length} 張` : ''}（共 ${r.pages} 頁）`
      )
    } catch (e) {
      setSheetState('')
      toast.error(`無法輸出：${errMsg(e)}`)
    } finally {
      setSheetBusy(false)
    }
  }

  const renderJob = job?.kind === 'render' && job.project === project ? job : undefined

  return (
    <section className="bg-card space-y-3 rounded-xl border p-3">
      <h2 className="text-muted-foreground text-xs font-semibold">輸出</h2>

      <div className="grid grid-cols-2 items-end gap-2">
        <div className="grid gap-1.5">
          <Label className="text-muted-foreground text-xs">上方畫面</Label>
          <Select value={String(cropY)} onValueChange={(v) => setCropY(Number(v))}>
            <SelectTrigger size="sm" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper" onCloseAutoFocus={(e) => e.preventDefault()}>
              <SelectItem value="0.5">置中裁切</SelectItem>
              <SelectItem value="0">保留上方</SelectItem>
              <SelectItem value="1">保留下方</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Label className="gap-2 pb-1.5 text-sm">
          <Switch checked={simile} onCheckedChange={setSimile} />
          重複小節用 % 記號
        </Label>
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={busy} title={busy ? BUSY_HINT : undefined} onClick={renderVideo}>
            {busy ? <Loader2 className="animate-spin" /> : <Video />}
            {readOnly ? '輸出練習影片' : '儲存並輸出練習影片'}
          </Button>
          {busy && <span className="text-muted-foreground text-xs">{BUSY_HINT}</span>}
        </div>
        {renderJob?.state === 'running' && (
          <div className="space-y-1" role="status">
            <div className="text-muted-foreground text-xs">
              {JOB_KIND_LABEL.render.running}（{renderJob.project}）{renderJob.step ?? ''}{' '}
              {Math.round((renderJob.progress ?? 0) * 100)}%
            </div>
            <Progress value={Math.round((renderJob.progress ?? 0) * 100)} className="h-1.5" />
          </div>
        )}
        {renderJob?.state === 'done' && (
          <p className="text-success text-xs break-all" role="status">
            完成：projects/{renderJob.project}/{renderJob.output ?? ''}
          </p>
        )}
        {renderJob?.state === 'error' && (
          <div role="alert" className="space-y-1">
            <p className="text-destructive text-xs font-medium">{JOB_KIND_LABEL.render.failed}</p>
            {renderJob.error && (
              <pre className="bg-destructive/10 text-destructive max-h-24 overflow-auto rounded-md p-2 font-mono text-[11px] whitespace-pre-wrap">
                {renderJob.error}
              </pre>
            )}
          </div>
        )}
      </div>

      <div className="space-y-2 border-t pt-3">
        <h3 className="text-muted-foreground text-xs font-semibold">鼓譜圖檔（A4 直式）</h3>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" disabled={sheetBusy} onClick={() => exportSheet('pdf')}>
            <FileText /> PDF
          </Button>
          <Button variant="outline" size="sm" disabled={sheetBusy} onClick={() => exportSheet('png')}>
            <FileImage /> PNG
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              api.openExports(project).catch((e) => toast.error(`無法開啟：${errMsg(e)}`))
            }
          >
            <FolderOpen /> 開啟輸出資料夾
          </Button>
        </div>
        <p className="text-muted-foreground text-xs break-all">
          {sheetState || '依目前選的鼓譜、上方 % 記號選項輸出'}
        </p>
      </div>
    </section>
  )
}
