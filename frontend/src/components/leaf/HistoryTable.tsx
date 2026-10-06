import { useState, useEffect } from 'react'
import { Trash2 } from 'lucide-react'
import Badge from '@/components/ui/Badge'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import { formatDate } from '@/lib/disease'
import type { CaseSummary } from '@/lib/leafApi'
import { leafTranslations } from '@/lib/leafTranslations'

interface HistoryTableProps {
  cases: CaseSummary[]
  onRowClick: (c: CaseSummary) => void
  onDelete: (caseId: string) => Promise<void>
}

export default function HistoryTable({ cases, onRowClick, onDelete }: HistoryTableProps) {
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [lang, setLang] = useState<'en' | 'si'>('en')

  useEffect(() => {
    const storedLang = localStorage.getItem('paddyguard_leaf_lang') as 'en' | 'si'
    if (storedLang) setLang(storedLang)
  }, [])

  const t = leafTranslations[lang]

  if (cases.length === 0) {
    return <EmptyState title={t.noHistoryTitle} description={t.noHistoryDesc} />
  }

  async function handleConfirmDelete() {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await onDelete(pendingDelete)
    } finally {
      setDeleting(false)
      setPendingDelete(null)
    }
  }

  return (
    <div className="overflow-x-auto rounded-2xl bg-white shadow-sm border border-beige/60">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-beige bg-beige/20 text-xs uppercase text-forest-muted">
          <tr>
            <th className="px-4 py-3">{t.caseId}</th>
            <th className="px-4 py-3">Date</th>
            <th className="px-4 py-3">{t.disease}</th>
            <th className="px-4 py-3">{t.confidence}</th>
            <th className="px-4 py-3">{t.severity}</th>
            <th className="px-4 py-3">{t.city}</th>
            <th className="px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => {
            const hasExpertLabel = !!(c as any).expert_validated_disease
            const expertLabel = (c as any).expert_validated_disease
            
            return (
              <tr
                key={c.case_id}
                onClick={() => onRowClick(c)}
                className="cursor-pointer border-b border-beige/60 last:border-0 hover:bg-beige/20 history-row"
              >
                <td className="px-4 py-3 font-mono text-xs text-forest-muted">
                  <div>{c.case_id.substring(0, 8)}...</div>
                  {c.needs_expert_review && c.review_status === 'pending' && (
                    <span className="text-[10px] text-amber font-semibold block mt-1">Review Required</span>
                  )}
                  {c.needs_expert_review && c.review_status === 'verified' && (
                    <span className="text-[10px] text-forest font-semibold block mt-1">Expert Verified</span>
                  )}
                </td>
                <td className="px-4 py-3 text-forest-light">{formatDate(c.created_at)}</td>
                <td className="px-4 py-3 font-medium text-forest">
                  {hasExpertLabel ? (
                    <div>
                      <del className="text-forest-muted/60 text-xs block">{c.predicted_disease?.replace(/_/g, ' ')}</del>
                      <strong className="text-forest font-bold text-sm">{expertLabel?.replace(/_/g, ' ')}</strong>
                    </div>
                  ) : (
                    <span>{c.predicted_disease?.replace(/_/g, ' ')}</span>
                  )}
                </td>
                <td className="px-4 py-3">{c.confidence ? `${(c.confidence * 100).toFixed(2)}%` : '-'}</td>
                <td className="px-4 py-3">
                  {c.severity_percentage != null ? (
                    <Badge tone={c.severity_percentage >= 30 ? 'red' : c.severity_percentage >= 15 ? 'amber' : 'green'}>
                      {c.severity_percentage.toFixed(1)}% ({c.severity_level || 'N/A'})
                    </Badge>
                  ) : (
                    '-'
                  )}
                </td>
                <td className="px-4 py-3 text-forest-light">{c.city || '-'}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setPendingDelete(c.case_id)
                    }}
                    className="rounded-lg p-1.5 text-red-soft hover:bg-red-soft/10"
                    title={t.removeBtn}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <ConfirmDialog
        isOpen={pendingDelete !== null}
        title={t.confirmDeleteTitle}
        message={t.confirmDeleteMsg}
        confirmLabel={t.deleteBtn}
        danger
        loading={deleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}
