import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Menu,
  Bell,
  ChevronDown,
  LogOut,
  ShieldCheck,
} from 'lucide-react'

import { useAuthStore } from '@/store/authStore'
import { usePestAuthStore } from '@/store/pestAuthStore'
import { clearLeafAuth, getLeafAuth } from '@/lib/leafApi'
import {
  getNotifications,
  markAllNotificationsRead,
  WEATHER_NOTIFICATION_EVENT,
  type StoredNotification,
} from '@/lib/weatherNotification'

const TITLES: Record<string, string> = {
  '/': 'මුල් පිටුව | Home',
  '/voice': 'හඬ රෝග නිර්ණය | Voice Diagnosis',
  '/leaf': 'කොළ රෝග හඳුනාගැනීම | Leaf Disease',
  '/pest': 'කෘමි හඳුනාගැනීම | Pest Detection',
  '/history': 'ඉතිහාසය | History',
  '/expert-review': 'Expert Review',
  '/dashboard': 'Admin Dashboard',
  '/expert-management': 'Expert Management',
  '/admin/users': 'User Management',
  '/pest-admin': 'Pest Model Administration',
}

export default function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [notifications, setNotifications] = useState<StoredNotification[]>([])
  const location = useLocation()
  const navigate = useNavigate()

  const farmerUser = useAuthStore(
    (state) => state.user,
  )

  const farmerLogout = useAuthStore(
    (state) => state.logout,
  )

  const pestAdminUser = usePestAuthStore(
    (state) => state.user,
  )

  const pestAdminAuthed = usePestAuthStore(
    (state) => state.isAuthenticated,
  )

  const pestAdminLogout = usePestAuthStore(
    (state) => state.logout,
  )

  const leafAuth = getLeafAuth()

  const displayEmail = pestAdminAuthed
    ? pestAdminUser?.username || 'Pest Admin'
    : farmerUser?.email || leafAuth?.username || ''

  const displayRole = pestAdminAuthed
    ? 'PEST ADMIN'
    : leafAuth?.role || (farmerUser ? 'FARMER' : '')

  const title = TITLES[location.pathname] || 'PaddyGuard AI'
  const unreadCount = notifications.filter((n) => !n.read).length

  useEffect(() => {
    const refresh = () => setNotifications(getNotifications())
    refresh()
    window.addEventListener(WEATHER_NOTIFICATION_EVENT, refresh)
    return () => window.removeEventListener(WEATHER_NOTIFICATION_EVENT, refresh)
  }, [])

  function handleLogout() {
    if (pestAdminAuthed) {
      pestAdminLogout()
      navigate('/pest-admin-login')
      return
    }

    clearLeafAuth()
    farmerLogout()
    navigate('/login')
  }

  function handleBellClick() {
    setNotifOpen((o) => !o)
    setDropdownOpen(false)
    if (!notifOpen) markAllNotificationsRead()
  }

  function formatTimeAgo(timestamp: number): string {
    const diffMs = Date.now() - timestamp
    const minutes = Math.floor(diffMs / 60000)
    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  return (
    <header className="flex h-16 items-center justify-between border-b border-beige bg-white px-4 md:px-6">

      <div className="flex items-center gap-3">

        <button
          onClick={onMenuClick}
          className="rounded-lg p-2 text-forest hover:bg-beige lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <h1 className="truncate font-sinhala text-base font-bold text-forest md:text-lg">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative">
          <button
            onClick={handleBellClick}
            className="relative rounded-full p-2 text-forest-muted hover:bg-beige"
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-soft text-[10px] font-bold text-white">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setNotifOpen(false)} />
              <div className="absolute right-0 top-full z-20 mt-2 w-80 max-w-[90vw] rounded-xl bg-white p-2 shadow-lg">
                <div className="border-b border-beige px-3 py-2">
                  <p className="text-sm font-semibold text-forest">Notifications</p>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <p className="px-3 py-4 text-center text-sm text-forest-muted">
                      No notifications yet
                    </p>
                  ) : (
                    notifications.map((n) => (
                      <div key={n.id} className="border-b border-beige px-3 py-2 last:border-b-0">
                        <p className="whitespace-pre-line text-sm text-forest">{n.body}</p>
                        <p className="mt-1 text-xs text-forest-muted">{formatTimeAgo(n.timestamp)}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="relative">

          <button
            onClick={() => {
              setDropdownOpen((o) => !o)
              setNotifOpen(false)
            }}
            className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 hover:bg-beige"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber text-sm font-bold text-white">
              {displayEmail
                .charAt(0)
                .toUpperCase() || 'U'}
            </div>

            <ChevronDown className="h-4 w-4 text-forest-muted" />
          </button>

          {dropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() =>
                  setDropdownOpen(false)
                }
              />

              <div className="absolute right-0 top-full z-20 mt-2 w-60 rounded-xl bg-white p-2 shadow-lg">

                <div className="border-b border-beige px-3 py-3">

                  {pestAdminAuthed && (
                    <div className="mb-2 flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-green-soft" />

                      <span className="rounded-full bg-green-soft/10 px-2 py-1 text-[10px] font-bold text-green-soft">
                        PEST ADMIN
                      </span>
                    </div>
                  )}

                  <p className="truncate text-sm font-semibold text-forest">
                    {displayEmail}
                  </p>

                  <p className="text-xs text-forest-muted">
                    {displayRole}
                  </p>
                </div>

                <button
                  onClick={handleLogout}
                  className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-soft hover:bg-red-soft/10"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}