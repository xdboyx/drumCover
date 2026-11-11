import { Check, Circle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

/** 步驟清單：已完成 ✓ → 目前步驟 ▶ 與百分比 → 待做 */
export function JobSteps({
  steps,
  index,
  progress,
  className,
}: {
  steps: string[]
  index: number
  progress: number
  className?: string
}) {
  const pct = Math.round(progress * 100)
  return (
    <ol className={cn('flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs', className)}>
      {steps.map((s, i) => (
        <li
          key={`${i}-${s}`}
          className={cn(
            'flex items-center gap-1',
            i < index && 'text-muted-foreground',
            i === index && 'text-foreground font-semibold',
            i > index && 'text-muted-foreground/70'
          )}
          aria-current={i === index ? 'step' : undefined}
        >
          {i < index ? (
            <Check className="text-success size-3" />
          ) : i === index ? (
            <Loader2 className="text-primary size-3 animate-spin" />
          ) : (
            <Circle className="size-2.5" />
          )}
          <span>{s}</span>
          {i === index && <span className="text-primary tabular-nums">{pct}%</span>}
          {i < steps.length - 1 && <span className="text-muted-foreground/50 ps-0.5">→</span>}
        </li>
      ))}
    </ol>
  )
}
