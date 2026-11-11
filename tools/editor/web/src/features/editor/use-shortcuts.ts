import { useEffect } from 'react'
import type { EditorActions } from './use-editor-actions'
import type { Playback } from './use-playback'
import { useEditorStore } from './store'

/** 焦點在這些元素內時不觸發快捷鍵（輸入框、下拉選單、對話框、選單） */
const IGNORE_SELECTOR =
  'input, textarea, select, [contenteditable="true"], [role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"], [role="combobox"]'
/** 這些元素自己會吃空白鍵（鍵盤 Tab 到按鈕再按空白＝按下按鈕） */
const SPACE_SELECTOR = 'button, a, summary, [role="switch"], [role="checkbox"]'

function isIgnored(target: EventTarget | null, key: string): boolean {
  if (!(target instanceof Element)) return false
  if (target.closest(IGNORE_SELECTOR)) return true
  return key === ' ' && !!target.closest(SPACE_SELECTOR)
}

/**
 * 快捷鍵：←/→ 換小節、空白 播放/停止、L 循環、Ctrl+Z/Y 復原重做、Ctrl+C/V 複製貼上小節、Ctrl+S 儲存。
 * 另外：點完按鈕後把焦點放掉，不然下一次按空白會再按一次同一顆按鈕。
 */
export function useShortcuts(actions: EditorActions, playback: Playback) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (isIgnored(e.target, e.key)) return
      if (!useEditorStore.getState().score) return
      const k = e.key.toLowerCase()
      const ctrl = e.ctrlKey || e.metaKey
      const cur = useEditorStore.getState().cur
      if (ctrl && k === 's') {
        e.preventDefault()
        void actions.save()
      } else if (ctrl && k === 'z') {
        e.preventDefault()
        actions.undo()
      } else if (ctrl && k === 'y') {
        e.preventDefault()
        actions.redo()
      } else if (ctrl && k === 'c') {
        // 有選取文字時讓瀏覽器照常複製
        if (!window.getSelection()?.toString()) actions.copy()
      } else if (ctrl && k === 'v') {
        actions.paste()
      } else if (ctrl || e.altKey) {
        return
      } else if (k === 'arrowleft') {
        e.preventDefault()
        playback.go(cur - 1)
      } else if (k === 'arrowright') {
        e.preventDefault()
        playback.go(cur + 1)
      } else if (k === ' ') {
        e.preventDefault()
        playback.toggle()
      } else if (k === 'l') {
        const s = useEditorStore.getState()
        s.setLoop(!s.loop)
      }
    }
    // 空白鍵的按鈕啟動發生在 keyup：被快捷鍵處理過的空白，不讓它再按一次焦點上的按鈕
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key === ' ' && !isIgnored(e.target, e.key)) e.preventDefault()
    }
    const onClick = (e: MouseEvent) => {
      const el = e.target instanceof Element ? e.target.closest('button') : null
      if (!el || el.closest('[role="dialog"], [role="alertdialog"], [role="menu"]')) return
      if (el.hasAttribute('aria-haspopup') || el.getAttribute('role') === 'combobox') return
      el.blur()
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('keyup', onKeyUp)
    document.addEventListener('click', onClick)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('keyup', onKeyUp)
      document.removeEventListener('click', onClick)
    }
  }, [actions, playback])
}
