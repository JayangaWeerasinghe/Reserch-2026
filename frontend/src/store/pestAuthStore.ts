import { create } from 'zustand'

export interface PestAdminUser {
  username: string
  role: 'PEST_ADMIN'
}

interface PestAuthState {
  user: PestAdminUser | null
  isAuthenticated: boolean
  login: (username: string, password: string) => boolean
  logout: () => void
}

const STORAGE_KEY = 'paddyguard_pest_auth'

const ADMIN_USERNAME = import.meta.env.VITE_PEST_ADMIN_USERNAME
const ADMIN_PASSWORD = import.meta.env.VITE_PEST_ADMIN_PASSWORD

function loadInitial(): Pick<PestAuthState, 'user' | 'isAuthenticated'> {
  const raw = localStorage.getItem(STORAGE_KEY)

  if (!raw) {
    return {
      user: null,
      isAuthenticated: false,
    }
  }

  try {
    const parsed = JSON.parse(raw)

    if (parsed?.user?.username === ADMIN_USERNAME && parsed?.user?.role === 'PEST_ADMIN') {
      return {
        user: parsed.user,
        isAuthenticated: true,
      }
    }

    localStorage.removeItem(STORAGE_KEY)

    return {
      user: null,
      isAuthenticated: false,
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY)

    return {
      user: null,
      isAuthenticated: false,
    }
  }
}

export const usePestAuthStore = create<PestAuthState>((set) => ({
  ...loadInitial(),

  login: (username, password) => {
    const valid =
      username.trim() === ADMIN_USERNAME &&
      password === ADMIN_PASSWORD

    if (!valid) {
      return false
    }

    const user: PestAdminUser = {
      username: ADMIN_USERNAME,
      role: 'PEST_ADMIN',
    }

    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        user,
      }),
    )

    set({
      user,
      isAuthenticated: true,
    })

    return true
  },

  logout: () => {
    localStorage.removeItem(STORAGE_KEY)

    set({
      user: null,
      isAuthenticated: false,
    })
  },
}))