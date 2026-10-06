import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  hoverable?: boolean
}

export default function Card({ children, hoverable = false, className = '', ...rest }: CardProps) {
  return (
    <div
      className={`rounded-2xl bg-white p-5 shadow-sm transition-shadow ${hoverable ? 'hover:shadow-md' : ''} ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}
