import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { staffLogin } from '@/lib/leafApi'
import { getErrorMessage } from '@/lib/api'

export default function StaffLogin() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (loading) return
    setError('')
    setLoading(true)
    try {
      const auth = await staffLogin(username, password)
      if (auth.role === 'SUPER_ADMIN') navigate('/dashboard')
      else if (auth.role === 'EXPERT') navigate('/expert-review')
      else navigate('/leaf')
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
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-forest">
          <ShieldCheck className="h-7 w-7 text-amber" />
        </div>
        <h1 className="text-2xl font-bold text-forest">PaddyGuard Staff Portal</h1>
        <p className="max-w-xs text-sm text-forest-muted">
          Authorized agricultural experts and research administrators only.
        </p>
      </div>

      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Username" value={username} onChange={(e) => setUsername(e.target.value)} required autoComplete="username" />
          <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />

          {error && <p className="rounded-xl bg-red-soft/10 px-4 py-2 text-sm text-red-soft">{error}</p>}

          <Button type="submit" size="lg" className="w-full" loading={loading}>
            Sign In
          </Button>
        </form>

        <div className="mt-6 border-t border-beige pt-4 text-center">
          <Link to="/login" className="text-xs text-forest-muted hover:text-forest">
            ← Back to farmer login
          </Link>
        </div>
      </div>
    </div>
  )
}
