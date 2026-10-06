import { create } from 'zustand'

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  role: 'FARMER'
}

interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  setAuth: (user: AuthUser, accessToken: string, refreshToken: string) => void
  logout: () => void
}

const STORAGE_KEY = 'paddyguard_auth'

function loadInitial(): Pick<AuthState, 'user' | 'accessToken' | 'refreshToken' | 'isAuthenticated'> {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return { user: null, accessToken: null, refreshToken: null, isAuthenticated: false }
  try {
    const parsed = JSON.parse(raw)
    return {
      user: parsed.user ?? null,
      accessToken: parsed.accessToken ?? null,
      refreshToken: parsed.refreshToken ?? null,
      isAuthenticated: Boolean(parsed.accessToken),
    }
  } catch {
    return { user: null, accessToken: null, refreshToken: null, isAuthenticated: false }
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  ...loadInitial(),
  setAuth: (user, accessToken, refreshToken) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ user, accessToken, refreshToken }))
    set({ user, accessToken, refreshToken, isAuthenticated: true })
  },
  logout: () => {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem('paddyguard_leaf_auth')
    sessionStorage.removeItem('paddyguard_leaf_analysis_state')
    set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false })
  },
}))
