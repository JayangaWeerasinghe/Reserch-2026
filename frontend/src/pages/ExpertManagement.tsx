import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import toast from 'react-hot-toast'
import { UserPlus } from 'lucide-react'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { createExpert, getExperts, toggleExpert } from '@/lib/leafApi'
import type { Expert } from '@/lib/leafApi'
import { formatDate } from '@/lib/disease'

export default function ExpertManagement() {
  const [experts, setExperts] = useState<Expert[]>([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [creating, setCreating] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setLoading(true)
    try {
      setExperts(await getExperts())
    } catch {
      toast.error('Failed to load experts')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!name || !username || !password) return
    setCreating(true)
    try {
      await createExpert(name, username, password)
      toast.success('Expert created')
      setName('')
      setUsername('')
      setPassword('')
      load()
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create expert'
      toast.error(message)
    } finally {
      setCreating(false)
    }
  }

  async function handleToggle(id: number) {
    setTogglingId(id)
    try {
      await toggleExpert(id)
      load()
    } catch {
      toast.error('Failed to update status')
    } finally {
      setTogglingId(null)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-1">
        <div className="mb-4 flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-amber" />
          <h3 className="font-semibold text-forest">Add Expert</h3>
        </div>
        <form onSubmit={handleCreate} className="space-y-3">
          <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
          <Input label="Username" value={username} onChange={(e) => setUsername(e.target.value)} required autoComplete="username" />
          <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
          <Button type="submit" className="w-full" loading={creating}>
            Create Expert
          </Button>
        </form>
      </Card>

      <Card className="lg:col-span-2">
        <h3 className="mb-4 font-semibold text-forest">Experts</h3>
        {loading ? (
          <LoadingSpinner labelEn="Loading experts..." />
        ) : experts.length === 0 ? (
          <p className="py-6 text-center text-sm text-forest-muted">No experts yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead className="border-b border-beige text-xs uppercase text-forest-muted">
                <tr>
                  <th className="py-2">Name</th>
                  <th className="py-2">Username</th>
                  <th className="py-2">Created</th>
                  <th className="py-2">Status</th>
                  <th className="py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {experts.map((ex) => (
                  <tr key={ex.id} className="border-b border-beige/60 last:border-0">
                    <td className="py-3 font-medium text-forest">{ex.name}</td>
                    <td className="py-3 text-forest-light">{ex.username}</td>
                    <td className="py-3 text-forest-light">{formatDate(ex.created_at)}</td>
                    <td className="py-3">
                      <Badge tone={ex.is_active ? 'green' : 'gray'}>{ex.is_active ? 'Active' : 'Disabled'}</Badge>
                    </td>
                    <td className="py-3 text-right">
                      <Button size="sm" variant="outline" onClick={() => handleToggle(ex.id)} loading={togglingId === ex.id}>
                        {ex.is_active ? 'Disable' : 'Enable'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
