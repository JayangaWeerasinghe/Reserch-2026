import { useState, useEffect } from 'react'
import Modal from '@/components/ui/Modal'
import Badge from '@/components/ui/Badge'
import { formatDate } from '@/lib/disease'
import type { CaseSummary } from '@/lib/leafApi'
import { leafTranslations } from '@/lib/leafTranslations'

interface ActivityModalProps {
  caseData: CaseSummary | null
  onClose: () => void
}

export default function ActivityModal({ caseData, onClose }: ActivityModalProps) {
  const [lang, setLang] = useState<'en' | 'si'>('en')

  useEffect(() => {
    const storedLang = localStorage.getItem('paddyguard_leaf_lang') as 'en' | 'si'
    if (storedLang) setLang(storedLang)
  }, [caseData]) // Refresh language preference when case details modal is opened

  if (!caseData) return null

  const t = leafTranslations[lang]
  const c = caseData as any

  const hasExpertLabel = !!c.expert_validated_disease
  const expertLabel = c.expert_validated_disease

  return (
    <Modal isOpen={Boolean(caseData)} onClose={onClose} title={t.caseDetailsTitle} size="lg">
      <div className="space-y-6 leaf-module">
        <div className="grid gap-4 sm:grid-cols-2">
          {c.original_image_url && (
            <div>
              <span className="block text-xs font-semibold text-forest-muted mb-1">{t.originalImage}</span>
              <img
                src={c.original_image_url}
                alt="Leaf Original"
                className="w-full h-48 rounded-xl object-contain border border-beige bg-beige/10"
                onError={(e) => {
                  ;(e.target as HTMLElement).style.display = 'none'
                }}
              />
            </div>
          )}
          {c.gradcam_image_url && (
            <div>
              <span className="block text-xs font-semibold text-forest-muted mb-1">{t.gradcamImage}</span>
              <img
                src={c.gradcam_image_url}
                alt="Leaf Grad-CAM"
                className="w-full h-48 rounded-xl object-contain border border-beige bg-beige/10"
                onError={(e) => {
                  ;(e.target as HTMLElement).style.display = 'none'
                }}
              />
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-beige/60 pb-3">
            <span className="font-mono text-sm font-bold text-forest">
              ID: {c.case_id}
            </span>
            <div className="flex items-center gap-2">
              <Badge tone={c.confidence >= 0.75 ? 'green' : 'amber'}>
                {t.confidence}: {c.confidence ? `${(c.confidence * 100).toFixed(2)}%` : '-'}
              </Badge>
              {c.needs_expert_review && (
                <Badge tone={c.review_status === 'verified' ? 'green' : 'amber'}>
                  {c.review_status === 'verified' ? 'Verified' : 'Pending Review'}
                </Badge>
              )}
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <div>
              <dt className="text-forest-muted">{lang === 'si' ? 'දිනය' : 'Date'}</dt>
              <dd className="font-medium text-forest">{formatDate(c.created_at)}</dd>
            </div>
            <div>
              <dt className="text-forest-muted">{t.city}</dt>
              <dd className="font-medium text-forest">{c.city || '-'}</dd>
            </div>
            <div>
              <dt className="text-forest-muted">{lang === 'si' ? 'AI පුරෝකථනය' : 'AI Prediction'}</dt>
              <dd className="font-medium text-forest">{c.predicted_disease?.replace(/_/g, ' ') || '-'}</dd>
            </div>
            {hasExpertLabel && (
              <div>
                <dt className="text-forest font-semibold">{t.expertLabel}</dt>
                <dd className="font-bold text-forest" style={{ color: '#1d7b4f' }}>
                  {expertLabel?.replace(/_/g, ' ')}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-forest-muted">{t.severity}</dt>
              <dd className="font-medium text-forest">
                {c.severity_percentage != null
                  ? `${c.severity_percentage.toFixed(1)}% (${c.severity_level || 'N/A'})`
                  : '-'}
              </dd>
            </div>
            {c.review_reason && (
              <div>
                <dt className="text-forest-muted">{t.reviewReason}</dt>
                <dd className="font-medium text-forest">{c.review_reason.replace(/_/g, ' ')}</dd>
              </div>
            )}
            <div>
              <dt className="text-forest-muted">{t.trainingStatus}</dt>
              <dd className="font-medium text-forest">
                {c.approved_for_training ? t.approved : t.notApproved}
                {c.consumed_by_job_id && (
                  <span className="text-xs text-forest-muted block">
                    ({t.consumedBy}: {c.consumed_by_job_id.substring(0, 10)}...)
                  </span>
                )}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </Modal>
  )
}
