const STEPS = [
  { title: '貼上來源', body: 'YouTube 網址或本機 mp4 都可以。' },
  { title: '自動扒譜', body: '下載、分離鼓聲、扒譜、排版，約需幾分鐘。' },
  { title: '修改與輸出', body: '在編輯器修改鼓譜，輸出練習影片或鼓譜圖檔。' },
]

/** 極簡的三步說明 */
export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" className="grid gap-3">
      <h2 id="how-title" className="text-sm font-semibold">
        怎麼運作
      </h2>
      <ol className="grid gap-3 sm:grid-cols-3">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex gap-3 sm:block">
            <span
              aria-hidden
              className="bg-muted text-muted-foreground flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold sm:mb-2"
            >
              {i + 1}
            </span>
            <div>
              <p className="text-sm font-medium">{s.title}</p>
              <p className="text-muted-foreground text-xs">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
