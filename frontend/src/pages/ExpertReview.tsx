import { useEffect, useState, useMemo } from 'react'
import toast from 'react-hot-toast'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { HelpCircle } from 'lucide-react'

// UI Primitives
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ConfirmDialog from '@/components/ui/ConfirmDialog'

// Scoped Leaf APIs
import { getReviewQueue, verifyCase, deleteCase, clearPendingReviewQueue, getLeafAuth } from '@/lib/leafApi'
import type { ReviewQueueItem } from '@/lib/leafApi'
import { formatDate } from '@/lib/disease'

import '@/components/leaf/leafStyles.css'

const CLASSES = [
  'Bacterial_Blight',
  'Brown_Spot',
  'Healthy',
  'Leaf_Blast',
  'OOD',
]
const EXTERNAL_LABELS = [
  { value: 'Bacterial_Blight', label: 'Bacterial Blight' },
  { value: 'Brown_Spot', label: 'Brown Spot' },
  { value: 'Healthy', label: 'Healthy' },
  { value: 'Leaf_Blast', label: 'Leaf Blast' },
  { value: 'OOD', label: 'OOD / Unknown' },
]
const PIE_COLORS = ['#2c7a7b', '#dd6b20', '#38a169', '#3182ce', '#805ad5', '#e53e3e']

const CustomTooltipPie = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ background: '#2c3e34', color: '#fff', padding: '8px 12px', borderRadius: '6px', fontSize: '0.8rem' }}>
        <p style={{ margin: 0, fontWeight: 'bold' }}>{payload[0].name}</p>
        <p style={{ margin: '4px 0 0' }}>{payload[0].value} case{payload[0].value !== 1 ? 's' : ''}</p>
      </div>
    )
  }
  return null
}

export default function ExpertReview() {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCase, setSelectedCase] = useState<ReviewQueueItem | null>(null)
  const [expertLabel, setExpertLabel] = useState(CLASSES[0])
  const [verifying, setVerifying] = useState(false)
  const [deletingCase, setDeletingCase] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [clearingQueue, setClearingQueue] = useState(false)
  const [clearQueueConfirmOpen, setClearQueueConfirmOpen] = useState(false)

  // Search Filters
  const [searchDisease, setSearchDisease] = useState('')
  const [searchCity, setSearchCity] = useState('')

  const canClearQueue = getLeafAuth()?.role === 'SUPER_ADMIN'

  useEffect(() => {
    loadQueue()
  }, [])

  const loadQueue = async () => {
    setLoading(true)
    try {
      const data = await getReviewQueue()
      setQueue(data)
    } catch {
      toast.error('Failed to load review queue')
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async () => {
    if (!selectedCase) return
    setVerifying(true)
    try {
      await verifyCase(selectedCase.case_id, expertLabel)
      toast.success(expertLabel === 'OOD' ? 'Case marked as OOD / Unknown' : 'Case verified successfully')
      setSelectedCase(null)
      await loadQueue()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to verify case'
      toast.error(detail)
    } finally {
      setVerifying(false)
    }
  }

  const handleDeleteCurrentCase = async () => {
    if (!selectedCase) return
    setDeletingCase(true)
    try {
      await deleteCase(selectedCase.case_id)
      toast.success('Review case deleted successfully')
      setDeleteConfirmOpen(false)
      setSelectedCase(null)
      await loadQueue()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to delete case'
      toast.error(detail)
    } finally {
      setDeletingCase(false)
    }
  }

  const handleClearQueue = async () => {
    setClearingQueue(true)
    try {
      const result = await clearPendingReviewQueue()
      setClearQueueConfirmOpen(false)
      toast.success(`${result.deleted_count} pending review case${result.deleted_count === 1 ? '' : 's'} cleared successfully.`)
      await loadQueue()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Failed to clear pending review queue'
      toast.error(detail)
    } finally {
      setClearingQueue(false)
    }
  }

  // Derived stats for disease charts
  const diseaseData = useMemo(() => {
    const counts: Record<string, number> = {}
    queue.forEach((c) => {
      const key = c.predicted_disease?.replace(/_/g, ' ') || 'Unknown'
      counts[key] = (counts[key] || 0) + 1
    })
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
  }, [queue])

  // Derived stats for city charts
  const cityData = useMemo(() => {
    const counts: Record<string, number> = {}
    queue.forEach((c) => {
      const key = c.city || 'Unknown'
      counts[key] = (counts[key] || 0) + 1
    })
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
  }, [queue])

  const filteredQueue = useMemo(() => {
    return queue.filter((c) => {
      const diseaseMatch =
        !searchDisease || c.predicted_disease?.toLowerCase().includes(searchDisease.toLowerCase())
      const cityMatch = !searchCity || (c.city || '').toLowerCase().includes(searchCity.toLowerCase())
      return diseaseMatch && cityMatch
    })
  }, [queue, searchDisease, searchCity])

  const diseaseOptions = useMemo(() => {
    return [...new Set(queue.map((c) => c.predicted_disease?.replace(/_/g, ' ')).filter(Boolean) as string[])]
  }, [queue])

  const cityOptions = useMemo(() => {
    return [...new Set(queue.map((c) => c.city).filter(Boolean) as string[])]
  }, [queue])

  if (loading) return <LoadingSpinner labelEn="Loading queue..." />

  return (
    <div className="leaf-module space-y-6">
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-1">
          <h2 className="text-xl font-bold text-forest" style={{ margin: 0 }}>Expert Review Queue</h2>
          {canClearQueue && !selectedCase && (
            <button
              type="button"
              onClick={() => setClearQueueConfirmOpen(true)}
              disabled={queue.length === 0}
              className="btn-secondary"
              style={{
                background: '#fff5f5',
                color: '#c53030',
                borderColor: '#feb2b2',
                width: 'auto',
                padding: '8px 14px',
                fontSize: '0.85rem',
                cursor: queue.length === 0 ? 'not-allowed' : 'pointer',
                opacity: queue.length === 0 ? 0.6 : 1,
              }}
            >
              {queue.length > 0 ? `Clear ${queue.length} Pending Cases` : 'No pending review cases to clear'}
            </button>
          )}
        </div>
        <p className="text-sm text-forest-muted mb-6">
          Expert workspace — review low-confidence rice leaf predictions selected for human verification.
        </p>

        {!selectedCase ? (
          <>
            {queue.length === 0 ? (
              <EmptyState
                title="Queue is empty"
                description="No predictions currently require expert verification. Great job!"
              />
            ) : (
              <div className="space-y-6">
                {/* Analytics Distribution Charts */}
                <div className="grid gap-6 md:grid-cols-2">
                  <div className="rounded-xl border border-beige bg-beige/10 p-4">
                    <h4 className="text-sm font-semibold text-forest mb-3">🦠 Review Requests by Disease</h4>
                    <div className="h-44 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={diseaseData}
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={65}
                            paddingAngle={3}
                            dataKey="value"
                          >
                            {diseaseData.map((entry, index) => (
                              <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip content={<CustomTooltipPie />} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex flex-wrap justify-center gap-3 mt-2 text-xs text-forest-muted">
                      {diseaseData.map((entry, index) => (
                        <span key={entry.name} className="flex items-center gap-1">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ background: PIE_COLORS[index % PIE_COLORS.length] }}
                          />
                          {entry.name} ({entry.value})
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-beige bg-beige/10 p-4">
                    <h4 className="text-sm font-semibold text-forest mb-3">📍 Review Requests by City</h4>
                    <div className="h-44 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={cityData}
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={65}
                            paddingAngle={3}
                            dataKey="value"
                          >
                            {cityData.map((entry, index) => (
                              <Cell key={entry.name} fill={PIE_COLORS[(index + 2) % PIE_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip content={<CustomTooltipPie />} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex flex-wrap justify-center gap-3 mt-2 text-xs text-forest-muted">
                      {cityData.map((entry, index) => (
                        <span key={entry.name} className="flex items-center gap-1">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ background: PIE_COLORS[(index + 2) % PIE_COLORS.length] }}
                          />
                          {entry.name} ({entry.value})
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex-1 min-w-[200px]">
                    <input
                      type="text"
                      list="disease-opts"
                      placeholder="Filter by disease..."
                      value={searchDisease}
                      onChange={(e) => setSearchDisease(e.target.value)}
                    />
                    <datalist id="disease-opts">
                      {diseaseOptions.map((d) => (
                        <option key={d} value={d} />
                      ))}
                    </datalist>
                  </div>
                  <div className="flex-1 min-w-[200px]">
                    <input
                      type="text"
                      list="city-opts"
                      placeholder="Filter by city..."
                      value={searchCity}
                      onChange={(e) => setSearchCity(e.target.value)}
                    />
                    <datalist id="city-opts">
                      {cityOptions.map((c) => (
                        <option key={c} value={c} />
                      ))}
                    </datalist>
                  </div>
                  {(searchDisease || searchCity) && (
                    <button
                      onClick={() => {
                        setSearchDisease('')
                        setSearchCity('')
                      }}
                      className="btn-secondary"
                      style={{ width: 'auto', padding: '11px 16px' }}
                    >
                      Clear
                    </button>
                  )}
                  <span className="text-xs text-forest-muted whitespace-nowrap ml-auto">
                    {filteredQueue.length} / {queue.length} shown
                  </span>
                </div>

                {/* Queue Table */}
                {filteredQueue.length === 0 ? (
                  <p className="text-center py-8 text-sm text-forest-muted">No cases match your filters.</p>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Case ID</th>
                          <th>Date</th>
                          <th>AI Prediction</th>
                          <th>Confidence</th>
                          <th>City</th>
                          <th>Selection Reason</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredQueue.map((item) => (
                          <tr key={item.case_id}>
                            <td className="font-mono text-xs text-forest-muted">
                              {item.case_id.substring(0, 12)}...
                            </td>
                            <td className="text-xs text-forest-muted">{formatDate(item.created_at)}</td>
                            <td className="font-medium text-forest">{item.predicted_disease?.replace(/_/g, ' ')}</td>
                            <td>
                              <span className={item.confidence < 0.6 ? 'text-red font-bold' : ''}>
                                {(item.confidence * 100).toFixed(2)}%
                              </span>
                            </td>
                            <td>{item.city || '—'}</td>
                            <td>
                              <div className="has-tooltip inline-flex items-center gap-1">
                                {item.review_reason === 'LOW_CONFIDENCE' && (
                                  <span className="text-red font-semibold text-xs">Critical Uncertainty</span>
                                )}
                                {item.review_reason === 'TOP_K_UNCERTAINTY' && (
                                  <span className="text-amber font-semibold text-xs">Top-K Borderline</span>
                                )}
                                {item.review_reason && (
                                  <>
                                    <HelpCircle className="h-3.5 w-3.5 text-forest-muted" />
                                    <div className="tooltip-popover" style={{ bottom: '25px', top: 'auto', width: '220px' }}>
                                      {item.review_reason === 'LOW_CONFIDENCE'
                                        ? "The AI's primary confidence score was below the safe threshold, meaning it is very uncertain."
                                        : 'The AI was torn between two closely competing diseases, indicating a borderline case.'}
                                    </div>
                                  </>
                                )}
                              </div>
                            </td>
                            <td>
                              <button
                                onClick={() => {
                                  setSelectedCase(item)
                                  setExpertLabel(item.predicted_disease)
                                }}
                                className="primary-btn text-xs py-1.5 px-3 rounded-lg"
                                style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
                              >
                                Review
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          /* Side-by-Side Review panel */
          <div className="space-y-6 animate-entrance border border-beige/60 bg-beige/5 p-6 rounded-xl">
            <div className="flex flex-wrap items-center justify-between border-b border-beige/60 pb-3">
              <h3 className="font-bold text-forest text-lg" style={{ margin: 0 }}>Reviewing Case</h3>
              <span className="font-mono text-xs bg-beige/40 text-forest px-3 py-1 rounded">
                ID: {selectedCase.case_id}
              </span>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {/* Image previews */}
              <div className="grid gap-4 grid-cols-2">
                <div>
                  <h4 className="text-xs font-bold text-forest-muted mb-2">Original Image</h4>
                  <div className="h-60 w-full flex items-center justify-center rounded-lg border border-beige bg-beige/10 overflow-hidden">
                    {selectedCase.original_image_url ? (
                      <img
                        src={selectedCase.original_image_url}
                        alt="Original Leaf"
                        className="max-h-full max-w-full object-contain"
                        onError={(e) => {
                          ;(e.target as HTMLElement).style.display = 'none'
                        }}
                      />
                    ) : (
                      <span className="text-xs text-forest-muted">Image not available</span>
                    )}
                  </div>
                </div>

                <div>
                  <h4 className="text-xs font-bold text-forest-muted mb-2">Grad-CAM Highlight</h4>
                  <div className="h-60 w-full flex items-center justify-center rounded-lg border border-beige bg-beige/10 overflow-hidden">
                    {selectedCase.gradcam_image_url ? (
                      <img
                        src={selectedCase.gradcam_image_url}
                        alt="Grad-CAM"
                        className="max-h-full max-w-full object-contain"
                        onError={(e) => {
                          ;(e.target as HTMLElement).style.display = 'none'
                        }}
                      />
                    ) : (
                      <span className="text-xs text-forest-muted">Grad-CAM not available</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Assessment Panel */}
              <div className="space-y-6">
                <div className="rounded-xl border border-beige bg-beige/10 p-4 space-y-3">
                  <h4 className="text-xs font-semibold text-forest-muted uppercase tracking-wider">
                    Model Assessment
                  </h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-forest-muted text-xs block">AI Prediction</span>
                      <strong className="text-forest text-base">
                        {selectedCase.predicted_disease?.replace(/_/g, ' ')}
                      </strong>
                    </div>
                    <div>
                      <span className="text-forest-muted text-xs block">Confidence</span>
                      <strong className="text-forest text-base">
                        {(selectedCase.confidence * 100).toFixed(2)}%
                      </strong>
                    </div>
                  </div>
                  <div>
                    <span className="text-forest-muted text-xs block">Flagged Reason</span>
                    <span className="text-amber font-semibold text-sm">
                      {selectedCase.review_reason?.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>

                <div className="rounded-xl border border-forest/10 bg-forest/5 p-4 space-y-4">
                  <label className="block text-sm font-bold text-forest">Provide Expert Verification:</label>
                  <select
                    value={expertLabel}
                    onChange={(e) => setExpertLabel(e.target.value)}
                    className="w-full rounded-xl border border-beige bg-white p-3 font-medium text-forest outline-none focus:border-forest"
                  >
                    {EXTERNAL_LABELS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>

                  <div className="flex gap-3">
                    <button
                      onClick={handleVerify}
                      disabled={verifying}
                      className="primary-submit-btn flex-1"
                      style={{ background: '#38a169', color: 'white' }}
                    >
                      {verifying ? 'Submitting...' : 'Submit Verification'}
                    </button>
                    <button
                      onClick={() => setDeleteConfirmOpen(true)}
                      className="btn-secondary"
                      style={{ background: '#fff5f5', color: '#c53030', borderColor: '#feb2b2', width: 'auto' }}
                    >
                      Delete Case
                    </button>
                    <button
                      onClick={() => setSelectedCase(null)}
                      className="btn-secondary"
                      style={{ background: 'white', color: '#4a5568', width: 'auto' }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={deleteConfirmOpen}
        title="Delete review case"
        message={`Delete this review case ${selectedCase?.case_id ?? 'Unknown'}? This permanently removes the case record and its uploaded image references from the leaf review workflow.`}
        confirmLabel="Delete Case"
        danger
        loading={deletingCase}
        onConfirm={handleDeleteCurrentCase}
        onCancel={() => setDeleteConfirmOpen(false)}
      />

      <ConfirmDialog
        isOpen={clearQueueConfirmOpen}
        title="Clear Review Queue?"
        message={`This will permanently remove all currently pending, unverified review cases from the Expert Review Queue.\n\nVerified, approved, consumed, and historical research records will not be removed.\n\nPending cases to remove: ${queue.length}`}
        confirmLabel={clearingQueue ? 'Clearing...' : 'Clear Pending Cases'}
        danger
        loading={clearingQueue}
        onConfirm={handleClearQueue}
        onCancel={() => setClearQueueConfirmOpen(false)}
      />
    </div>
  )
}
