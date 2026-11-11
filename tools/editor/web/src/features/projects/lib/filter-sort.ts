import type { ProjectListItem } from '@/lib/types'

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

export type SortKey = 'updated' | 'name'

/**
 * 名稱過濾（不分大小寫、忽略頭尾空白）＋排序。
 * 最近更新：沒有時間的（扒譜中、失敗）排最前面，因為通常是使用者現在最關心的。
 */
export function filterAndSort(
  items: readonly ProjectListItem[],
  query: string,
  sort: SortKey
): ProjectListItem[] {
  const q = query.trim().toLowerCase()
  const list = q ? items.filter((p) => p.name.toLowerCase().includes(q)) : [...items]
  if (sort === 'name') return list.sort((a, b) => collator.compare(a.name, b.name))
  return list.sort((a, b) => {
    const ta = a.updated ? Date.parse(a.updated) : Infinity
    const tb = b.updated ? Date.parse(b.updated) : Infinity
    if (ta !== tb) return tb > ta ? 1 : -1
    return collator.compare(a.name, b.name)
  })
}
