import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { getAdminUsers } from '@/lib/leafApi'
import type { AdminUser } from '@/lib/leafApi'
import { formatDate } from '@/lib/disease'

export default function AdminUsers() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAdminUsers()
      .then(setUsers)
      .catch(() => toast.error('Failed to load users'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner labelEn="Loading users..." />
  if (users.length === 0) return <EmptyState title="No users found" />

  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="border-b border-beige text-xs uppercase text-forest-muted">
            <tr>
              <th className="py-2">Name</th>
              <th className="py-2">Email</th>
              <th className="py-2">Joined</th>
              <th className="py-2">Analyses</th>
              <th className="py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id} className="border-b border-beige/60 last:border-0">
                <td className="py-3 font-medium text-forest">{u.name}</td>
                <td className="py-3 text-forest-light">{u.email}</td>
                <td className="py-3 text-forest-light">{formatDate(u.created_at)}</td>
                <td className="py-3">{u.analysis_count}</td>
                <td className="py-3">
                  <Badge tone={u.is_active ? 'green' : 'gray'}>{u.is_active ? 'Active' : 'Inactive'}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
