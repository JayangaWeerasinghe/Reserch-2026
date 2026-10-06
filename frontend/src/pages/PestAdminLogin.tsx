import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bug, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'

import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { usePestAuthStore } from '@/store/pestAuthStore'

export default function PestAdminLogin() {
  const navigate = useNavigate()

  const login = usePestAuthStore((state) => state.login)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()

    if (loading) return

    setError('')

    if (!username.trim() || !password) {
      setError('Please enter username and password.')
      return
    }

    setLoading(true)

    try {
      const success = login(username, password)

      if (!success) {
        const message = 'Invalid Pest Admin username or password.'
        setError(message)
        toast.error(message)
        return
      }

      toast.success('Pest Admin login successful.')
      navigate('/pest-admin')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream px-4 py-10">
      <div className="w-full max-w-md">

        <div className="mb-6 flex flex-col items-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-forest shadow-lg">
            <Bug className="h-8 w-8 text-amber" />
          </div>

          <h1 className="mt-4 text-2xl font-bold text-forest">
            Pest Admin Portal
          </h1>

          <p className="mt-2 max-w-sm text-sm leading-5 text-forest-muted">
            Authorized administrator access for pest model training,
            few-shot learning and research model management.
          </p>
        </div>

        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <div className="mb-6 flex items-center gap-3 rounded-xl border border-green-soft/20 bg-green-soft/5 p-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-soft/10">
              <ShieldCheck className="h-5 w-5 text-green-soft" />
            </div>

            <div>
              <p className="text-sm font-bold text-forest">
                Pest Model Administration
              </p>
              <p className="mt-1 text-xs leading-4 text-forest-muted">
                Fine-tuning is restricted to Pest Admin users.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Enter admin username"
              autoComplete="username"
              required
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter admin password"
              autoComplete="current-password"
              required
            />

            {error && (
              <div className="rounded-xl border border-red-soft/20 bg-red-soft/5 px-4 py-3 text-sm text-red-soft">
                {error}
              </div>
            )}

            <Button
              type="submit"
              size="lg"
              className="w-full"
              loading={loading}
            >
              Sign In to Pest Admin
            </Button>
          </form>

          <div className="mt-6 border-t border-beige pt-4 text-center">
            <Link
              to="/login"
              className="text-xs text-forest-muted transition hover:text-forest"
            >
              ← Back to farmer login
            </Link>
          </div>
        </div>

        <p className="mt-5 text-center text-[11px] text-forest-muted">
          PaddyGuard AI · Pest Detection Research Module
        </p>
      </div>
    </div>
  )
}