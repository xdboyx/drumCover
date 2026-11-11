import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { summarizeError } from '@/lib/error-summary'
import { cn } from '@/lib/utils'

/** 錯誤訊息：預設只顯示一行摘要，長內容可展開看完整原文。 */
export function ErrorDetails({
  message,
  prefix,
  className,
}: {
  message: string
  /** 摘要前的白話說明，例如「失敗步驟：分離鼓聲」 */
  prefix?: string
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const { summary, hasMore } = summarizeError(message)
  return (
    <div className={cn('text-destructive text-sm', className)} role="alert">
      {prefix && <p className="text-destructive/80 text-xs">{prefix}</p>}
      {summary && <p className="break-words">{summary}</p>}
      {hasMore && (
        <>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground mt-1 inline-flex items-center gap-1 rounded text-xs underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:outline-none"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            <ChevronDown className={cn('size-3 transition-transform', open && 'rotate-180')} />
            {open ? '收合完整錯誤' : '顯示完整錯誤'}
          </button>
          {open && (
            <pre className="bg-destructive/10 mt-1.5 max-h-48 overflow-auto rounded-md p-2 font-mono text-xs whitespace-pre-wrap">
              {message}
            </pre>
          )}
        </>
      )}
    </div>
  )
}
