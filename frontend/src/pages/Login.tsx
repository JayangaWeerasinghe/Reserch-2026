import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Wheat } from 'lucide-react'
import toast from 'react-hot-toast'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { login, getProfile } from '@/lib/authApi'
import { ensureLeafSession } from '@/lib/leafApi'
import { useAuthStore } from '@/store/authStore'
import { getErrorMessage } from '@/lib/api'

export default function Login() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (loading) return
    setError('')
    setLoading(true)
    try {
      const tokens = await login(email, password)
      setAuth({ id: '', email, full_name: null, role: 'FARMER' }, tokens.access_token, tokens.refresh_token)

      const profile = await getProfile()
      setAuth({ id: profile.id, email: profile.email, full_name: profile.full_name, role: 'FARMER' }, tokens.access_token, tokens.refresh_token)

      ensureLeafSession(email, password, profile.full_name || undefined)
      navigate('/')
    } catch (err: unknown) {
      const message = getErrorMessage(err, 'Login failed. Please try again.')
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-cream px-4 py-10">
      <div className="mb-6 flex flex-col items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-forest">
          <Wheat className="h-7 w-7 text-amber" />
        </div>
        <h1 className="text-2xl font-bold text-forest">PaddyGuard AI</h1>
        <p className="font-sinhala text-sm text-forest-muted">ගොවිජන රෝග නිර්ණය පද්ධතිය</p>
        <p className="text-xs text-forest-muted">AI-Powered Rice Disease Diagnosis for Sri Lankan Farmers</p>
      </div>

      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <h2 className="mb-6 font-sinhala text-xl font-bold text-forest">ගිණුමට ඇතුළු වන්න</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="විද්‍යුත් තැපෑල | Email"
            sinhalaLabel
            type="email"
            placeholder="farmer@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <Input
            label="මුරපදය | Password"
            sinhalaLabel
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />

          {error && <p className="rounded-xl bg-red-soft/10 px-4 py-2 text-sm text-red-soft">{error}</p>}

          <Button type="submit" size="lg" className="w-full font-sinhala" loading={loading}>
            ඇතුළු වන්න | Login
          </Button>
        </form>

        <p className="mt-5 text-center font-sinhala text-sm text-forest">
          ගිණුමක් නැද්ද?{' '}
          <Link to="/register" className="font-semibold text-amber">
            ලියාපදිංචි වන්න
          </Link>
        </p>

        <div className="mt-6 border-t border-beige pt-4 text-center space-y-2">
          <Link to="/staff-login" className="block text-xs text-forest-muted hover:text-forest">
            Staff / Expert login →
          </Link>
          <Link to="/pest-admin-login" className="block text-xs text-forest-muted hover:text-forest">
            Pest Admin login →
          </Link>
        </div>
      </div>
    </div>
  )
}
