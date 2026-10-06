import type { ReactNode } from 'react'

type Tone = 'amber' | 'green' | 'red' | 'blue' | 'gray' | 'forest'

interface BadgeProps {
  children: ReactNode
  tone?: Tone
  className?: string
}

const TONE_CLASSES: Record<Tone, string> = {
  amber: 'bg-amber-light text-amber-dark',
  green: 'bg-green-soft/15 text-green-soft',
  red: 'bg-red-soft/15 text-red-soft',
  blue: 'bg-blue-soft/15 text-blue-soft',
  gray: 'bg-gray-muted/15 text-gray-muted',
  forest: 'bg-forest/10 text-forest',
}

export default function Badge({ children, tone = 'forest', className = '' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${TONE_CLASSES[tone]} ${className}`}>
      {children}
    </span>
  )
}
