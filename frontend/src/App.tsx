import { useEffect } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import ProtectedRoute from '@/components/layout/ProtectedRoute'
import { scheduleWeatherChecks } from '@/lib/weatherNotification'
import { useAuthStore } from '@/store/authStore'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import StaffLogin from '@/pages/StaffLogin'

import Home from '@/pages/Home'
import VoiceDiagnosis from '@/pages/VoiceDiagnosis'
import LeafDisease from '@/pages/LeafDisease'
import PestDetection from '@/pages/PestDetection'
import TreatmentChat from '@/pages/TreatmentChat'
import History from '@/pages/History'
import ExpertReview from '@/pages/ExpertReview'

import AdminDashboard from '@/pages/AdminDashboard'
import ExpertManagement from '@/pages/ExpertManagement'
import AdminUsers from '@/pages/AdminUsers'

import PestAdminLogin from '@/pages/PestAdminLogin'
import PestAdminDashboard from '@/pages/PestAdminDashboard'

import { usePestAuthStore } from '@/store/pestAuthStore'

function Protected({
  allow,
  children,
}: {
  allow: Array<'FARMER' | 'EXPERT' | 'SUPER_ADMIN'>
  children: React.ReactNode
}) {
  return (
    <ProtectedRoute allow={allow}>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

function PestAdminProtected({
  children,
}: {
  children: React.ReactNode
}) {
  const isAuthenticated = usePestAuthStore(
    (state) => state.isAuthenticated,
  )

  if (!isAuthenticated) {
    return <Navigate to="/pest-admin-login" replace />
  }

  return (
    <AppShell>
      {children}
    </AppShell>
  )
}

export default function App() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  useEffect(() => {
    if (isAuthenticated) {
      scheduleWeatherChecks()
    }
  }, [isAuthenticated])

  return (
    <Routes>
      {/* Normal authentication */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/staff-login" element={<StaffLogin />} />

      {/* Farmer */}
      <Route
        path="/"
        element={
          <Protected allow={['FARMER']}>
            <Home />
          </Protected>
        }
      />

      <Route
        path="/voice"
        element={
          <Protected allow={['FARMER']}>
            <VoiceDiagnosis />
          </Protected>
        }
      />

      {/* Leaf */}
      <Route
        path="/leaf"
        element={
          <Protected
            allow={['FARMER', 'EXPERT', 'SUPER_ADMIN']}
          >
            <LeafDisease />
          </Protected>
        }
      />

      {/* Pest detection for farmers */}
      <Route
        path="/pest"
        element={
          <Protected allow={['FARMER']}>
            <PestDetection />
          </Protected>
        }
      />

      <Route
        path="/chat"
        element={
          <Protected allow={['FARMER']}>
            <TreatmentChat />
          </Protected>
        }
      />

      {/* General history */}
      <Route
        path="/history"
        element={
          <Protected
            allow={['FARMER', 'EXPERT', 'SUPER_ADMIN']}
          >
            <History />
          </Protected>
        }
      />

      {/* Existing staff system */}
      <Route
        path="/expert-review"
        element={
          <Protected
            allow={['EXPERT', 'SUPER_ADMIN']}
          >
            <ExpertReview />
          </Protected>
        }
      />

      <Route
        path="/dashboard"
        element={
          <Protected allow={['SUPER_ADMIN']}>
            <AdminDashboard />
          </Protected>
        }
      />

      <Route
        path="/expert-management"
        element={
          <Protected allow={['SUPER_ADMIN']}>
            <ExpertManagement />
          </Protected>
        }
      />

      <Route
        path="/admin/users"
        element={
          <Protected allow={['SUPER_ADMIN']}>
            <AdminUsers />
          </Protected>
        }
      />

      {/* ============================= */}
      {/* Pest Admin System             */}
      {/* ============================= */}

      <Route
        path="/pest-admin-login"
        element={<PestAdminLogin />}
      />

      <Route
        path="/pest-admin"
        element={
          <PestAdminProtected>
            <PestAdminDashboard />
          </PestAdminProtected>
        }
      />

      {/* Fallback */}
      <Route
        path="*"
        element={<Navigate to="/" replace />}
      />
    </Routes>
  )
}