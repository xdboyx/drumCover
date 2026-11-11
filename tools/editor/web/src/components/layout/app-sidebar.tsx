import { Link, useRouterState } from '@tanstack/react-router'
import { AudioLines, Drum, FolderOpen, Loader2 } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import { JobStatusPanel } from '@/components/job-status'
import { useJob } from '@/hooks/use-job'

const NAV = [
  { title: '扒譜', to: '/', icon: AudioLines, match: (p: string) => p === '/' },
  {
    title: '我的專案',
    to: '/projects',
    icon: FolderOpen,
    // 編輯器是從某個專案開啟的，視為「我的專案」的下一層
    match: (p: string) => p.startsWith('/projects') || p.startsWith('/editor'),
  },
] as const

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { isMobile, setOpenMobile } = useSidebar()
  const { job } = useJob()
  const scoring = job?.state === 'running' && (job.kind === 'import' || job.kind === 'reimport')
  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader className="p-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="鼓譜編輯器">
              <Link to="/" onClick={() => isMobile && setOpenMobile(false)}>
                <div className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <Drum className="size-4" />
                </div>
                <div className="grid flex-1 text-start text-sm leading-tight">
                  <span className="truncate font-semibold">鼓譜編輯器</span>
                  <span className="text-muted-foreground truncate text-xs">drumCover</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup className="px-3 py-2">
          <SidebarGroupLabel>導覽</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton asChild tooltip={item.title} isActive={item.match(pathname)}>
                    <Link to={item.to} onClick={() => isMobile && setOpenMobile(false)}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                  {item.to === '/projects' && scoring && (
                    <SidebarMenuBadge aria-label="有專案正在扒譜">
                      <Loader2 className="text-primary size-3.5 animate-spin" />
                    </SidebarMenuBadge>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-3 group-data-[collapsible=icon]:hidden">
        <div className="bg-sidebar-accent/50 rounded-lg border p-3">
          <div className="text-muted-foreground mb-2 text-xs font-medium">工作狀態</div>
          <JobStatusPanel />
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
