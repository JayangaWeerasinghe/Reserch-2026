import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { getLeafAuth } from '@/lib/leafApi'

export type AppRole = 'FARMER' | 'EXPERT' | 'SUPER_ADMIN'

export function defaultRouteFor(): string {
  const leafAuth = getLeafAuth()
  if (leafAuth?.role === 'SUPER_ADMIN') return '/dashboard'
  if (leafAuth?.role === 'EXPERT') return '/expert-review'
  if (useAuthStore.getState().isAuthenticated) return '/'
  return '/login'
}

interface ProtectedRouteProps {
  allow: AppRole[]
  children: ReactNode
}

export default function ProtectedRoute({ allow, children }: ProtectedRouteProps) {
  const farmerAuthed = useAuthStore((s) => s.isAuthenticated)
  const leafAuth = getLeafAuth()
  const leafRole = leafAuth?.role

  const granted =
    (allow.includes('FARMER') && farmerAuthed) ||
    (allow.includes('EXPERT') && (leafRole === 'EXPERT' || leafRole === 'SUPER_ADMIN')) ||
    (allow.includes('SUPER_ADMIN') && leafRole === 'SUPER_ADMIN')

  if (!granted) {
    if (!farmerAuthed && !leafAuth) return <Navigate to="/login" replace />
    return <Navigate to={defaultRouteFor()} replace />
  }

  return <>{children}</>
}
