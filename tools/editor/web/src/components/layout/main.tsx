import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

const WIDTH = {
  /** 單一任務的表單頁 */
  form: 'mx-auto w-full max-w-2xl',
  /** 清單頁 */
  list: 'mx-auto w-full max-w-4xl',
} as const

/**
 * 內容區。預設用滿寬度（編輯器需要很寬的工作區）；
 * 傳 `width` 會限制成置中的閱讀寬度：`form` 約 672px、`list` 約 896px。
 */
export function Main({
  width,
  className,
  ...props
}: ComponentProps<'main'> & { width?: keyof typeof WIDTH }) {
  return (
    <main
      className={cn('min-w-0 flex-1 p-3 sm:p-4 lg:p-6', width && WIDTH[width], className)}
      {...props}
    />
  )
}
