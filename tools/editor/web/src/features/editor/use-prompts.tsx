import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

export interface NameOptions {
  title: string
  description?: string
  okLabel: string
  initial?: string
  placeholder?: string
}

export interface ConfirmOptions {
  title: string
  description?: string
  okLabel: string
  destructive?: boolean
}

export type LeaveChoice = 'save' | 'discard' | 'cancel'

type Pending =
  | { kind: 'name'; opts: NameOptions; resolve: (v: string | null) => void }
  | { kind: 'confirm'; opts: ConfirmOptions; resolve: (v: boolean) => void }
  | { kind: 'leave'; resolve: (v: LeaveChoice) => void }

export interface Prompts {
  /** 跳出命名對話框；取消回傳 null，否則回傳去掉前後空白的名稱 */
  askName: (opts: NameOptions) => Promise<string | null>
  askConfirm: (opts: ConfirmOptions) => Promise<boolean>
  /** 有未存修改時問：存檔後切換／放棄修改／取消 */
  askLeave: () => Promise<LeaveChoice>
}

function NameForm({
  opts,
  onDone,
}: {
  opts: NameOptions
  onDone: (name: string | null) => void
}) {
  const [name, setName] = useState(opts.initial ?? '')
  const trimmed = name.trim()
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (trimmed) onDone(trimmed)
      }}
    >
      <DialogHeader>
        <DialogTitle>{opts.title}</DialogTitle>
        {opts.description && <DialogDescription>{opts.description}</DialogDescription>}
      </DialogHeader>
      <Input
        autoFocus
        className="my-4"
        value={name}
        maxLength={60}
        placeholder={opts.placeholder ?? '例如：照原譜版'}
        aria-label="版本名稱"
        onChange={(e) => setName(e.target.value)}
      />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onDone(null)}>
          取消
        </Button>
        <Button type="submit" disabled={!trimmed}>
          {opts.okLabel}
        </Button>
      </DialogFooter>
    </form>
  )
}

/**
 * 命名、確認、未存修改三種對話框，包成「await 就能拿到答案」的函式。
 * 回傳的 element 要放進元件樹（通常在頁面最外層）。Esc／點外面都視為取消。
 */
export function usePrompts(): { prompts: Prompts; element: ReactNode } {
  const [pending, setPending] = useState<Pending | null>(null)
  const resolverRef = useRef<((v: never) => void) | null>(null)

  // 元件卸載時若對話框還開著，當成取消，不讓呼叫端一直等
  useEffect(
    () => () => {
      const r = resolverRef.current as ((v: unknown) => void) | null
      resolverRef.current = null
      r?.(null)
    },
    []
  )

  const open = useCallback(<T,>(make: (resolve: (v: T) => void) => Pending) => {
    return new Promise<T>((resolve) => {
      const wrapped = (v: T) => {
        resolverRef.current = null
        setPending(null)
        resolve(v)
      }
      resolverRef.current = wrapped as (v: never) => void
      setPending(make(wrapped))
    })
  }, [])

  const askName = useCallback(
    (opts: NameOptions) => open<string | null>((resolve) => ({ kind: 'name', opts, resolve })),
    [open]
  )
  const askConfirm = useCallback(
    (opts: ConfirmOptions) => open<boolean>((resolve) => ({ kind: 'confirm', opts, resolve })),
    [open]
  )
  const askLeave = useCallback(
    () => open<LeaveChoice>((resolve) => ({ kind: 'leave', resolve })),
    [open]
  )

  const element = (
    <>
      <Dialog
        open={pending?.kind === 'name'}
        onOpenChange={(o) => !o && pending?.kind === 'name' && pending.resolve(null)}
      >
        <DialogContent showCloseButton={false}>
          {pending?.kind === 'name' && (
            <NameForm opts={pending.opts} onDone={(n) => pending.resolve(n)} />
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={pending?.kind === 'confirm'}
        onOpenChange={(o) => !o && pending?.kind === 'confirm' && pending.resolve(false)}
      >
        <DialogContent showCloseButton={false}>
          {pending?.kind === 'confirm' && (
            <>
              <DialogHeader>
                <DialogTitle>{pending.opts.title}</DialogTitle>
                {pending.opts.description && (
                  <DialogDescription>{pending.opts.description}</DialogDescription>
                )}
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => pending.resolve(false)}>
                  取消
                </Button>
                <Button
                  variant={pending.opts.destructive ? 'destructive' : 'default'}
                  onClick={() => pending.resolve(true)}
                >
                  {pending.opts.okLabel}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={pending?.kind === 'leave'}
        onOpenChange={(o) => !o && pending?.kind === 'leave' && pending.resolve('cancel')}
      >
        <DialogContent showCloseButton={false}>
          {pending?.kind === 'leave' && (
            <>
              <DialogHeader>
                <DialogTitle>目前的修改還沒儲存</DialogTitle>
                <DialogDescription>要怎麼處理這些修改？</DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => pending.resolve('cancel')}>
                  取消
                </Button>
                <Button variant="outline" onClick={() => pending.resolve('discard')}>
                  放棄修改
                </Button>
                <Button onClick={() => pending.resolve('save')}>存檔後切換</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  )

  return { prompts: { askName, askConfirm, askLeave }, element }
}
