import { Redo2, Save, Undo2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useEditor } from './context'
import { useEditorStore } from './store'
import { VersionMenu } from './version-menu'

/** Header 內的工具列：版本選單與動作、儲存狀態、復原／重做、儲存。 */
export function EditorToolbar() {
  const { actions, readOnly } = useEditor()
  const dirty = useEditorStore((s) => s.dirty)
  const canUndo = useEditorStore((s) => s.history.undo.length > 0)
  const canRedo = useEditorStore((s) => s.history.redo.length > 0)

  return (
    <>
      <VersionMenu />
      <div className="flex-1" />
      {dirty ? (
        <Badge variant="outline" className="border-warning text-warning shrink-0" role="status">
          ● 有未儲存的修改
        </Badge>
      ) : (
        <Badge variant="outline" className="border-success text-success hidden shrink-0 sm:inline-flex" role="status">
          已儲存
        </Badge>
      )}
      <Button
        variant="ghost"
        size="sm"
        title="復原 (Ctrl+Z)"
        aria-label="復原"
        disabled={!canUndo}
        onClick={actions.undo}
      >
        <Undo2 /> <span className="hidden 2xl:inline">復原</span>
      </Button>
      <Button
        variant="ghost"
        size="sm"
        title="重做 (Ctrl+Y)"
        aria-label="重做"
        disabled={!canRedo}
        onClick={actions.redo}
      >
        <Redo2 /> <span className="hidden 2xl:inline">重做</span>
      </Button>
      <Button
        size="sm"
        title={readOnly ? '唯讀的鼓譜不能存檔' : '儲存 (Ctrl+S)'}
        disabled={readOnly}
        onClick={() => void actions.save()}
      >
        <Save /> 儲存
      </Button>
    </>
  )
}
