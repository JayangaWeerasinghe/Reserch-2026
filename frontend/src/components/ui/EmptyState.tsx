import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}

export default function EmptyState({ icon: Icon = Inbox, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-2xl bg-white p-10 text-center shadow-sm">
      <Icon className="mb-2 h-10 w-10 text-forest-muted/50" />
      <p className="font-semibold text-forest">{title}</p>
      {description && <p className="max-w-sm text-sm text-forest-muted">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}
