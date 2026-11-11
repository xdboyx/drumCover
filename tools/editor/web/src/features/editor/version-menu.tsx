import { useNavigate } from '@tanstack/react-router'
import { Copy, MoreHorizontal, Pencil, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useJob } from '@/hooks/use-job'
import { useEditor } from './context'
import { versionLabel } from './lib/version'

/** 版本選單（切換＝改網址的 v，未存修改由頁面的 blocker 詢問）＋版本動作（複製、改名、刪除、重新扒譜）。 */
export function VersionMenu() {
  const { project, version, versions, readOnly, actions } = useEditor()
  const navigate = useNavigate()
  const { busy } = useJob()
  const current = versions.find((v) => v.id === version)

  return (
    <div className="flex min-w-0 items-center gap-1">
      <Select
        value={version}
        onValueChange={(v) =>
          void navigate({ to: '/editor', search: { p: project, v: v === 'ai' ? undefined : v } })
        }
      >
        <SelectTrigger size="sm" className="w-44 sm:w-56" aria-label="版本">
          <SelectValue placeholder="版本" />
        </SelectTrigger>
        <SelectContent position="popper" onCloseAutoFocus={(e) => e.preventDefault()}>
          {versions.map((v) => (
            <SelectItem key={v.id} value={v.id}>
              {versionLabel(v)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label="版本動作" title="版本動作">
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" onCloseAutoFocus={(e) => e.preventDefault()}>
          <DropdownMenuItem onSelect={() => void actions.copyVersion()}>
            <Copy /> 複製版本…
          </DropdownMenuItem>
          <DropdownMenuItem disabled={readOnly || !current} onSelect={() => void actions.renameVersion()}>
            <Pencil /> 改名…
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            disabled={readOnly || !current}
            onSelect={() => void actions.deleteVersion()}
          >
            <Trash2 /> 刪除版本…
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            disabled={busy}
            title="用目前的扒譜程式重新扒譜；上一份 AI 譜會保存成舊 AI 譜，編輯版本不受影響"
            onSelect={() => void actions.reimport()}
          >
            <RefreshCw /> 重新扒譜…
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
