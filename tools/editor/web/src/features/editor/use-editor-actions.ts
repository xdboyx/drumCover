import { useNavigate } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useRefreshJob } from '@/hooks/use-job'
import * as api from '@/lib/api'
import type { Bar, VersionInfo } from '@/lib/types'
import {
  applyBarContent,
  barContent,
  clearBar,
  restoreBarContent,
  toggleNote,
  toggleTriplet,
} from './lib/bar'
import { isReadOnlyVersion } from './lib/version'
import type { Playback } from './use-playback'
import type { Prompts } from './use-prompts'
import { useEditorStore } from './store'

export const versionsKey = (project: string) => ['versions', project] as const

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export interface EditorActions {
  save: () => Promise<boolean>
  /** 有未存修改時問使用者；回傳 false 代表取消 */
  confirmLeave: () => Promise<boolean>
  /** 把版本載入記憶體並切過去（更新網址） */
  switchVersion: (version: string) => Promise<void>
  copyVersion: () => Promise<void>
  renameVersion: () => Promise<void>
  deleteVersion: () => Promise<void>
  reimport: () => Promise<void>
  toggleNote: (tick: number, inst: string) => void
  toggleTriplet: (beat: number) => void
  copyPrev: () => void
  copy: () => void
  paste: () => void
  clear: () => void
  revert: () => void
  undo: () => void
  redo: () => void
}

/** 抓鼓譜並放進 store（同專案保留目前小節） */
export async function fetchIntoStore(project: string, version: string): Promise<void> {
  const d = await api.getScore(project, version)
  useEditorStore.getState().load({
    project,
    version,
    score: d.score,
    act: d.act,
    media: d.media,
  })
}

/**
 * 編輯器的所有動作：儲存、版本管理、修改小節（含唯讀時先建立新版本）、復原重做。
 * 失敗一律用 toast 顯示伺服器回的訊息，不丟出例外。
 */
export function useEditorActions(
  project: string,
  prompts: Prompts,
  playback: Playback
): EditorActions {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const refreshJob = useRefreshJob()
  const store = useEditorStore

  const versionList = () => qc.getQueryData<VersionInfo[]>(versionsKey(project))
  const currentVersion = () => store.getState().loaded?.version ?? 'ai'
  const readOnly = () => isReadOnlyVersion(currentVersion(), versionList())
  const refreshVersions = () => qc.invalidateQueries({ queryKey: versionsKey(project) })
  const gotoVersion = (v: string) =>
    navigate({ to: '/editor', search: { p: project, v: v === 'ai' ? undefined : v } })

  async function save(): Promise<boolean> {
    const s = store.getState()
    if (!s.score || !s.loaded) return false
    if (readOnly()) {
      toast.info('這份鼓譜是唯讀的')
      return false
    }
    const { project: p, version: v } = s.loaded
    const rev = s.rev
    try {
      const r = await api.saveScore(p, v, s.score)
      const fresh = await api.getScore(p, v)
      store.getState().markSaved(fresh.score, rev)
      toast.success(`已儲存（共 ${r.edited} 個小節有手動修改）`)
      return true
    } catch (e) {
      toast.error(`儲存失敗：${errMsg(e)}`)
      return false
    }
  }

  async function confirmLeave(): Promise<boolean> {
    if (!store.getState().dirty) return true
    const choice = await prompts.askLeave()
    if (choice === 'save') return save()
    return choice === 'discard'
  }

  /** 載入某版本、更新版本清單、再改網址（順序不能反：網址對上已載入的版本，頁面就不會重抓） */
  async function switchVersion(version: string) {
    await fetchIntoStore(project, version)
    await refreshVersions()
    await gotoVersion(version)
  }

  /**
   * 要改鼓譜前呼叫。唯讀的鼓譜先請使用者命名一個新的編輯版本，建立後切過去（保留目前小節）。
   * 回傳 false 代表使用者取消或建立失敗，這次修改不要做。
   */
  async function ensureEditable(): Promise<boolean> {
    if (!readOnly()) return true
    const name = await prompts.askName({
      title: '命名新版本',
      description: 'AI 譜是唯讀的。要修改的話，會先複製成一個新的編輯版本，再套用這次修改。',
      okLabel: '建立並修改',
    })
    if (!name) return false
    try {
      const v = await api.createVersion(project, { name, source: currentVersion() })
      await switchVersion(v.id)
      toast.success(`已建立新版本「${name}」`)
      return true
    } catch (e) {
      toast.error(`無法修改：${errMsg(e)}`)
      return false
    }
  }

  async function edit(fn: (b: Bar) => Bar) {
    if (!(await ensureEditable())) return
    store.getState().editBar(fn)
  }

  async function copyVersion() {
    if (!(await confirmLeave())) return
    const name = await prompts.askName({
      title: '複製成新版本',
      description: '從目前這份鼓譜複製出新的編輯版本。',
      okLabel: '複製',
    })
    if (!name) return
    try {
      const v = await api.createVersion(project, { name, source: currentVersion() })
      await switchVersion(v.id)
      toast.success(`已複製成新版本「${name}」`)
    } catch (e) {
      toast.error(`複製失敗：${errMsg(e)}`)
    }
  }

  async function renameVersion() {
    const id = currentVersion()
    const old = versionList()?.find((v) => v.id === id)
    if (!old) return
    const name = await prompts.askName({
      title: '改名',
      description: '幫這個編輯版本取新的名稱。',
      okLabel: '改名',
      initial: old.name,
    })
    if (!name || name === old.name) return
    try {
      await api.renameVersion(project, id, name)
      await refreshVersions()
      toast.success('已改名')
    } catch (e) {
      toast.error(`改名失敗：${errMsg(e)}`)
    }
  }

  async function deleteVersion() {
    const id = currentVersion()
    const old = versionList()?.find((v) => v.id === id)
    if (!old) return
    const ok = await prompts.askConfirm({
      title: `刪除版本「${old.name}」？`,
      description: '此動作無法復原。',
      okLabel: '刪除',
      destructive: true,
    })
    if (!ok) return
    try {
      await api.deleteVersion(project, id)
      store.getState().markClean()
      await switchVersion('ai')
      toast.success('已刪除版本')
    } catch (e) {
      toast.error(`刪除失敗：${errMsg(e)}`)
    }
  }

  async function reimport() {
    if (!(await confirmLeave())) return
    const ok = await prompts.askConfirm({
      title: '重新扒譜？',
      description:
        '重新扒譜會把目前的 AI 譜保存成唯讀的舊 AI 譜，你的編輯版本不會改變。確定要開始嗎？',
      okLabel: '開始重新扒譜',
    })
    if (!ok) return
    try {
      await api.projectReimport(project)
      refreshJob()
    } catch (e) {
      toast.error(`無法重新扒譜：${errMsg(e)}`)
    }
  }

  /** 修改類動作的錯誤統一處理 */
  const run = (p: Promise<void>) => void p.catch((e) => toast.error(`無法修改：${errMsg(e)}`))

  return {
    save,
    confirmLeave,
    switchVersion,
    copyVersion,
    renameVersion,
    deleteVersion,
    reimport,
    toggleNote: (tick, inst) => run(edit((b) => toggleNote(b, tick, inst))),
    toggleTriplet: (beat) => run(edit((b) => toggleTriplet(b, beat))),
    copyPrev: () => {
      const { score, cur } = store.getState()
      if (!score || cur === 0) return
      const content = barContent(score.bars[cur - 1])
      run(edit((b) => applyBarContent(b, content)))
    },
    copy: () => {
      store.getState().copyBar()
      toast.success(`已複製第 ${store.getState().cur + 1} 小節`)
    },
    paste: () => {
      const clip = store.getState().clip
      if (!clip) {
        toast.info('還沒有複製任何小節')
        return
      }
      run(edit((b) => applyBarContent(b, clip)))
    },
    clear: () => run(edit(clearBar)),
    revert: () =>
      run(
        (async () => {
          if (!(await ensureEditable())) return
          const { loaded, cur } = store.getState()
          if (!loaded) return
          const src = await api.restoreBar(loaded.project, loaded.version, cur)
          store.getState().editBar((b) => restoreBarContent(b, src))
          toast.success('已還原成來源版本')
        })()
      ),
    undo: () => {
      store.getState().undo()
      playback.go(store.getState().cur)
    },
    redo: () => {
      store.getState().redo()
      playback.go(store.getState().cur)
    },
  }
}
