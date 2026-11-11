import { ChevronDown, Keyboard } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="bg-muted rounded border border-b-2 px-1 font-mono text-[11px]">{children}</kbd>
  )
}

/** 操作說明（預設收合）。 */
export function HelpPanel() {
  return (
    <Collapsible className="bg-card rounded-xl border">
      <CollapsibleTrigger className="text-muted-foreground group flex w-full items-center gap-2 px-3 py-2 text-xs font-semibold">
        <Keyboard className="size-4" /> 操作說明
        <ChevronDown className="ml-auto size-4 transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="text-muted-foreground list-disc space-y-1.5 px-8 pb-3 text-xs leading-relaxed">
          <li>方格每一列是一種鼓、每一格是一個 16 分音符，點一下新增／刪除音符。每拍上方的「3」可切換成三連音。</li>
          <li>
            格子的<b className="text-primary">藍色深淺</b>＝AI 覺得那裡有擊打的程度；
            <b className="text-warning">橘點</b>＝寫的和 AI 聽到的不太一致，值得用耳朵確認。
          </li>
          <li>
            快捷鍵：<Kbd>←</Kbd> <Kbd>→</Kbd> 換小節、<Kbd>空白</Kbd> 播放／停止、<Kbd>L</Kbd> 循環、
            <Kbd>Ctrl</Kbd>+<Kbd>Z</Kbd>/<Kbd>Y</Kbd> 復原／重做、<Kbd>Ctrl</Kbd>+<Kbd>C</Kbd>/
            <Kbd>V</Kbd> 複製／貼上小節、<Kbd>Ctrl</Kbd>+<Kbd>S</Kbd> 儲存。
          </li>
          <li>
            AI 譜是唯讀的；在 AI 譜上做任何修改，會先請你命名一個新的編輯版本（存在專案的{' '}
            <code>versions/</code>），再套用修改。用上方的版本選單切換。
          </li>
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}
