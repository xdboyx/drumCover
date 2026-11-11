import { createFileRoute } from '@tanstack/react-router'
import { ProjectsPage } from '@/features/projects'

export const Route = createFileRoute('/projects')({
  component: ProjectsPage,
})
