import { useState, type ReactNode } from 'react'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { AppSidebar } from '@/components/layout/app-sidebar'

function readSidebarOpen(): boolean {
  try {
    return localStorage.getItem('dce.sidebar') !== 'closed'
  } catch {
    return true
  }
}

/**
 * App shell：可收合 sidebar + 內容區（SidebarInset）。
 * 頁面自己渲染 <Header> 與 <Main>：
 *   <Header title="…">工具列</Header>
 *   <Main>…</Main>
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(readSidebarOpen)
  return (
    <SidebarProvider
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        try {
          localStorage.setItem('dce.sidebar', o ? 'open' : 'closed')
        } catch {
          // 忽略
        }
      }}
    >
      <AppSidebar />
      <SidebarInset className="min-w-0">{children}</SidebarInset>
    </SidebarProvider>
  )
}
