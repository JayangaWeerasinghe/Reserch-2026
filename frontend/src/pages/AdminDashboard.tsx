import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts'
import { UploadCloud, ChevronDown } from 'lucide-react'

// UI Primitives
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Modal from '@/components/ui/Modal'
import ConfirmDialog from '@/components/ui/ConfirmDialog'

// Scoped Leaf components
import FineTuningPanel from '@/components/leaf/FineTuningPanel'

// Scoped Leaf APIs
import {
  getDashboardStats,
  prepareBatch,
  getBatches,
  getBatch,
  exportBatch,
  uploadCandidateModel,
  getCandidateModels,
  getDeployedModel,
  deleteCandidateModel,
  deleteActiveLearningBatch,
  getLeafAuth,
} from '@/lib/leafApi'
import type { DashboardStats, Batch, CandidateModel } from '@/lib/leafApi'

import '@/components/leaf/leafStyles.css'

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [batches, setBatches] = useState<Batch[]>([])
  const [selectedBatch, setSelectedBatch] = useState<any>(null)
  const [error, setError] = useState('')
  const [warningModalOpen, setWarningModalOpen] = useState(false)
  const [deployedModel, setDeployedModel] = useState<any>(null)
  const [isPreparingBatch, setIsPreparingBatch] = useState(false)
  const [isExportingBatch, setIsExportingBatch] = useState(false)
  const [loading, setLoading] = useState(true)
  const [compareCandidate, setCompareCandidate] = useState<CandidateModel | null>(null)
  const [candidateToDelete, setCandidateToDelete] = useState<CandidateModel | null>(null)
  const [batchToDelete, setBatchToDelete] = useState<Batch | null>(null)
  const [candidateDeleteLoading, setCandidateDeleteLoading] = useState(false)
  const [batchDeleteLoading, setBatchDeleteLoading] = useState(false)
  const [workflowTab, setWorkflowTab] = useState<'offline' | 'inapp'>('inapp')
  const [governanceExpanded, setGovernanceExpanded] = useState(false)
  const governanceRef = useRef<HTMLElement>(null)
  const [researchExpanded, setResearchExpanded] = useState(false)

  // Candidate evaluation states
  const [candidates, setCandidates] = useState<CandidateModel[]>([])
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateModel | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [testAccuracy, setTestAccuracy] = useState('')
  const [macroF1, setMacroF1] = useState('')
  const [sourceBatchId, setSourceBatchId] = useState('')
  const [notes, setNotes] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState('')

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const st = await getDashboardStats()
      setStats(st)
      const bs = await getBatches()
      setBatches(bs)
      
      // Load candidate models with error fallback
      try {
        const cs = await getCandidateModels()
        setCandidates(cs)
        if (cs.length > 0) {
          setSelectedCandidate(cs[0])
        }
      } catch {
        console.warn('Candidate models endpoint not fully accessible via Gateway')
      }

      // Load deployed model with error fallback
      try {
        const dm = await getDeployedModel()
        setDeployedModel(dm)
      } catch {
        console.warn('Deployed model endpoint not fully accessible via Gateway')
      }
    } catch {
      setError('Failed to load dashboard statistics')
    } finally {
      setLoading(false)
    }
  }

  async function handlePrepareClick() {
    if (stats && stats.active_learning_eligible_samples < 100) {
      setWarningModalOpen(true)
    } else {
      executePrepare()
    }
  }

  async function executePrepare() {
    setWarningModalOpen(false)
    setIsPreparingBatch(true)
    try {
      await prepareBatch()
      toast.success('Batch prepared successfully')
      await loadData()
    } catch (err: any) {
      if (err.response?.status === 400) {
        toast.error(err.response?.data?.detail || 'No eligible verified samples are currently available for a new Active Learning batch.')
      } else {
        toast.error(err.response?.data?.detail || 'Failed to prepare batch')
      }
    } finally {
      setIsPreparingBatch(false)
    }
  }

  async function viewBatch(batchId: string) {
    try {
      const data = await getBatch(batchId)
      setSelectedBatch(data)
    } catch {
      toast.error('Failed to load batch details')
    }
  }

  async function handleExportClick() {
    if (!selectedBatch) return
    setIsExportingBatch(true)
    try {
      const blob = await exportBatch(selectedBatch.batch.batch_id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `PaddyGuard_AL_BATCH_${selectedBatch.batch.batch_id}.zip`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      toast.success('Zip archive downloaded')
      await viewBatch(selectedBatch.batch.batch_id)
      loadData()
    } catch (err: any) {
      if (err.response?.status === 404) {
        toast.error('Export endpoint is not declared on the Gateway. Batch zip must be generated offline.')
      } else {
        toast.error('Failed to export batch archive')
      }
    } finally {
      setIsExportingBatch(false)
    }
  }

  const canDeleteLeafRecords = getLeafAuth()?.role === 'SUPER_ADMIN'

  const openCandidateComparison = (candidate: CandidateModel) => {
    setCompareCandidate(candidate)
    setSelectedCandidate(candidate)
    setGovernanceExpanded(true)
    governanceRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function confirmCandidateDelete() {
    if (!candidateToDelete) return
    setCandidateDeleteLoading(true)
    try {
      await deleteCandidateModel(candidateToDelete.candidate_id)
      toast.success('Candidate deleted successfully.')
      setCandidateToDelete(null)
      const refreshed = await getCandidateModels()
      setCandidates(refreshed)
      if (selectedCandidate?.candidate_id === candidateToDelete.candidate_id) {
        setSelectedCandidate(refreshed[0] ?? null)
      }
      if (compareCandidate?.candidate_id === candidateToDelete.candidate_id) {
        setCompareCandidate(null)
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to delete candidate model.'
      toast.error(message)
    } finally {
      setCandidateDeleteLoading(false)
    }
  }

  async function confirmBatchDelete() {
    if (!batchToDelete) return
    setBatchDeleteLoading(true)
    try {
      await deleteActiveLearningBatch(batchToDelete.batch_id)
      toast.success('Batch deleted successfully.')
      setBatchToDelete(null)
      const refreshed = await getBatches()
      setBatches(refreshed)
      if (selectedBatch?.batch?.batch_id === batchToDelete.batch_id) {
        setSelectedBatch(null)
      }
    } catch (err: any) {
      const status = err.response?.status
      const backendMessage = err.response?.data?.detail || err.response?.data?.message
      const warningMessage =
        status === 409
          ? (backendMessage || 'Cannot delete this batch because it is currently linked to training or model records.')
          : (backendMessage || 'Failed to delete batch.')

      toast.error(warningMessage)
      if (status !== 409) {
        console.error('Batch delete failed:', err)
      }
    } finally {
      setBatchDeleteLoading(false)
    }
  }

  async function handleUploadSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) {
      setUploadError('Please select a .pth model file.')
      return
    }
    if (!testAccuracy || !macroF1) {
      setUploadError('Please fill in both Accuracy and Macro F1.')
      return
    }

    setIsUploading(true)
    setUploadError('')
    setUploadSuccess('')

    const formData = new FormData()
    formData.append('file', file)
    formData.append('test_accuracy', testAccuracy)
    formData.append('macro_f1', macroF1)
    formData.append('source_batch_id', sourceBatchId)
    formData.append('notes', notes)

    try {
      const res = await uploadCandidateModel(formData)
      setUploadSuccess(`Successfully uploaded and validated ${res.filename}! Decision: ${res.decision}`)
      setFile(null)
      
      const fileInput = document.getElementById('candidate-file-input') as HTMLInputElement
      if (fileInput) fileInput.value = ''
      
      setTestAccuracy('')
      setMacroF1('')
      setSourceBatchId('')
      setNotes('')
      
      const cs = await getCandidateModels()
      setCandidates(cs)
      const uploaded = cs.find((c) => c.filename === res.filename)
      if (uploaded) {
        setSelectedCandidate(uploaded)
      } else if (cs.length > 0) {
        setSelectedCandidate(cs[0])
      }
    } catch (err: any) {
      if (err.response?.status === 404) {
        setUploadError('Upload API route is not declared on the Gateway. Candidates must be registered directly in database.')
      } else {
        setUploadError(err.response?.data?.detail || err.message || 'Failed to upload candidate model.')
      }
    } finally {
      setIsUploading(false)
    }
  }

  if (loading) return <LoadingSpinner labelEn="Loading research dashboard..." />

  return (
    <div className="leaf-module space-y-6">
      {/* 1. Fine-Tuning Workflows */}
      <section className="card space-y-6">
        <div>
          <p className="eyebrow">Model Fine-Tuning &amp; Candidate Management</p>
          <h2 className="text-xl font-bold text-forest mb-1" style={{ margin: 0 }}>Choose a Fine-Tuning Workflow</h2>
          <p className="text-sm text-forest-muted">
            PaddyGuard supports both controlled offline research retraining and integrated in-app PyTorch fine-tuning.
          </p>
        </div>

        {/* Workflow Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-beige/60">
          <button
            type="button"
            onClick={() => setWorkflowTab('offline')}
            className={`px-4 py-2.5 text-sm font-bold rounded-t-lg transition-colors ${
              workflowTab === 'offline' ? 'bg-forest text-white' : 'bg-beige/10 text-forest-muted hover:bg-beige/30'
            }`}
            style={{ width: 'auto' }}
          >
            Option 1: Colab Fine-Tuning
          </button>
          <button
            type="button"
            onClick={() => setWorkflowTab('inapp')}
            className={`px-4 py-2.5 text-sm font-bold rounded-t-lg transition-colors ${
              workflowTab === 'inapp' ? 'bg-forest text-white' : 'bg-beige/10 text-forest-muted hover:bg-beige/30'
            }`}
            style={{ width: 'auto' }}
          >
            Option 2: In-App Fine-Tuning
          </button>
        </div>

        {workflowTab === 'offline' ? (
          <div className="space-y-6 animate-entrance">
            {/* Option 1 explanation */}
            <div className="rounded-xl border border-beige bg-beige/10 p-5 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <span className="eyebrow">Option 1</span>
                  <h3 className="font-bold text-forest text-base" style={{ margin: 0 }}>Offline / Google Colab Fine-Tuning</h3>
                </div>
                <span className="analytics-panel__badge">Research / Offline Workflow</span>
              </div>
              <p className="text-sm text-forest-muted">
                Export expert-verified training samples, fine-tune the deployed model externally in Google Colab, generate a new .pth candidate checkpoint, then upload the candidate here for evaluation against the current deployed model.
              </p>
              <p className="text-xs text-forest-muted italic">
                Best for larger controlled experiments, GPU training, reproducibility, and Colab-based retraining.
              </p>
              <div className="flex flex-wrap items-center gap-2 pt-2 text-xs font-semibold text-forest">
                {[
                  'Expert Verified Samples',
                  'Export Training Batch',
                  'Google Colab Fine-Tuning',
                  'Generate Candidate .pth',
                  'Upload Candidate',
                  'Held-out Evaluation',
                  'Compare with Current Model',
                  'Reject / Eligible for Promotion',
                ].map((step, i, arr) => (
                  <span key={step} className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-full bg-white border border-beige">{step}</span>
                    {i < arr.length - 1 && <span className="text-forest-muted">&rarr;</span>}
                  </span>
                ))}
              </div>
            </div>

            {/* Prepare Next Active Learning Batch */}
            {stats && (
              <div className="rounded-xl border border-beige bg-beige/10 p-5 space-y-3">
                <h3 className="font-bold text-forest text-sm">Prepare Next Active Learning Batch</h3>
                <p className="text-xs text-forest-muted">
                  <strong>Research recommendation:</strong> Wait until at least 100 expert-verified samples are collected before starting the next controlled retraining round.
                </p>
                <div className="text-sm font-semibold text-forest flex flex-wrap gap-x-6 gap-y-1">
                  <span>Available verified samples: <strong className="text-forest">{stats.active_learning_eligible_samples}</strong></span>
                  <span>Mode: <strong>{stats.active_learning_eligible_samples < 100 ? 'DEMO' : 'CONTROLLED'}</strong></span>
                </div>

                {stats.active_learning_eligible_samples > 0 ? (
                  <button
                    onClick={handlePrepareClick}
                    disabled={isPreparingBatch}
                    className="primary-submit-btn w-auto"
                    style={{ width: 'auto', padding: '10px 20px', fontSize: '0.85rem' }}
                  >
                    {isPreparingBatch ? 'Preparing Batch...' : 'Prepare Next Batch'}
                  </button>
                ) : (
                  <button disabled className="btn-secondary" style={{ cursor: 'not-allowed', width: 'auto' }}>
                    No expert-verified samples available
                  </button>
                )}
              </div>
            )}

            {/* Prepared Batches List */}
            {batches.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-bold text-forest text-sm">Prepared Batches</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Batch ID</th>
                        <th>Created At</th>
                        <th>Samples</th>
                        <th>Status</th>
                        <th>Mode</th>
                        <th className="text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batches.map((b) => (
                        <tr key={b.batch_id} style={{ background: selectedBatch?.batch?.batch_id === b.batch_id ? '#f4fbf6' : 'none' }}>
                          <td className="font-mono text-xs text-forest-muted">{b.batch_id}</td>
                          <td className="text-xs text-forest-muted">{new Date(b.created_at).toLocaleString()}</td>
                          <td className="text-xs text-forest">{b.sample_count}</td>
                          <td className="font-semibold text-xs text-forest">{b.status}</td>
                          <td className="text-xs font-semibold">
                            {b.is_demo_mode ? <span className="text-amber">DEMO</span> : <span className="text-forest">RESEARCH</span>}
                          </td>
                          <td className="text-right">
                            <div className="flex justify-end gap-2">
                              <button
                                onClick={() => viewBatch(b.batch_id)}
                                className="primary-btn text-xs py-1 px-2.5 rounded-lg"
                                style={{ width: 'auto', padding: '4px 10px', fontSize: '0.8rem' }}
                              >
                                View
                              </button>
                              {canDeleteLeafRecords && (
                                <button
                                  onClick={() => setBatchToDelete(b)}
                                  disabled={b.status === 'TRAINING' || b.status === 'TRAINING_SIMULATION'}
                                  title={
                                    b.status === 'TRAINING' || b.status === 'TRAINING_SIMULATION'
                                      ? 'Cannot delete: this batch is used by a training job.'
                                      : undefined
                                  }
                                  className={`text-xs py-1 px-2.5 rounded-lg ${
                                    b.status === 'TRAINING' || b.status === 'TRAINING_SIMULATION'
                                      ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                                      : 'bg-red-500 hover:bg-red-600 text-white'
                                  }`}
                                  style={{ width: 'auto', padding: '4px 10px', fontSize: '0.8rem' }}
                                >
                                  Delete
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Selected Batch Details */}
            {selectedBatch && (
              <div className="rounded-xl border border-beige/60 bg-white p-5 space-y-6 animate-entrance">
                <div>
                  <h3 className="font-bold text-forest text-base" style={{ margin: 0 }}>Batch Details</h3>
                  <p className="text-xs text-forest-muted">
                    Batch metadata and verification checklist.
                  </p>
                </div>

          <div className="grid gap-4 md:grid-cols-2 text-sm text-forest">
            <div className="space-y-1">
              <p><strong>Batch ID:</strong> <span className="font-mono text-xs text-forest-light">{selectedBatch.batch.batch_id}</span></p>
              <p><strong>Verified Samples:</strong> {selectedBatch.batch.sample_count}</p>
              <p><strong>Recommended Samples:</strong> {selectedBatch.batch.recommended_batch_size}</p>
              <p><strong>Status:</strong> {selectedBatch.batch.status}</p>
            </div>
            <div
              className="rounded-xl border p-4"
              style={{
                background: selectedBatch.batch.is_demo_mode ? '#fffaf0' : '#f0fff4',
                borderColor: selectedBatch.batch.is_demo_mode ? '#feebc8' : '#c6f6d5',
              }}
            >
              {selectedBatch.batch.is_demo_mode ? (
                <>
                  <h4 className="font-bold text-amber mb-1">DEMO MODE</h4>
                  <p className="text-xs text-amber-700">This batch is below the recommended research batch size.</p>
                </>
              ) : (
                <>
                  <h4 className="font-bold text-forest mb-1">CONTROLLED RETRAINING BATCH READY</h4>
                  <p className="text-xs text-forest-muted">Retraining batch meets all research sizing requirements.</p>
                </>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="font-bold text-forest text-sm">Batch Samples</h3>
            <div className="table-wrap" style={{ maxHeight: '240px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Case ID</th>
                    <th>AI Prediction</th>
                    <th>Confidence</th>
                    <th>Expert Label</th>
                    <th>Selection Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedBatch.samples.map((s: any) => (
                    <tr key={s.case_id}>
                      <td className="font-mono text-xs text-forest-muted">{s.case_id}</td>
                      <td className="text-xs text-forest">{s.predicted_disease?.replace(/_/g, ' ')}</td>
                      <td className="text-xs text-forest">{(s.confidence * 100).toFixed(2)}%</td>
                      <td className="text-xs font-bold text-forest-light">{s.expert_validated_disease?.replace(/_/g, ' ')}</td>
                      <td className="text-xs text-forest-muted">{s.review_reason?.replace(/_/g, ' ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {selectedBatch.batch.status === 'READY' && (
            <div className="rounded-xl border border-beige bg-beige/10 p-5 space-y-4">
              <h3 className="font-bold text-forest text-sm">retraining &amp; Offline Export</h3>
              <p className="text-xs text-forest-muted">
                Exports expert-verified samples and original images for controlled offline retraining. Deployed model remains unchanged until a candidate is promoted.
              </p>
              
              {selectedBatch.batch.is_demo_mode && (
                <div className="rounded-xl bg-amber/5 border border-amber/20 p-3 text-xs text-amber-700">
                  <strong>Prototype Demonstration Mode:</strong> Demo batches may contain fewer than 100 samples. Exporting demonstrates the pipeline but does not make them equivalent to a controlled research round.
                </div>
              )}

              <button
                onClick={handleExportClick}
                disabled={isExportingBatch}
                className="primary-submit-btn w-auto"
                style={{ width: 'auto', padding: '10px 20px', background: '#2c7a7b' }}
              >
                {isExportingBatch ? 'Exporting Batch...' : 'Export Batch for Colab'}
              </button>
              
              {selectedBatch.batch.export_count > 0 && (
                <div className="text-xs text-forest font-semibold mt-2">
                  ✓ Exported for Colab ({new Date(selectedBatch.batch.exported_at).toLocaleString()})
                </div>
              )}
            </div>
          )}

          {/* Workflow Retraining Steps */}
          <div className="space-y-4 border-t border-beige/60 pt-4">
            <h3 className="font-bold text-forest text-sm">Retraining Workflow Tracker</h3>
            <p className="text-xs text-forest-muted">
              Retraining and validation are conducted offline. Deployed model: <strong>{deployedModel?.checkpoint || 'PaddyGuard_active_learning_round2.pth'}</strong>.
            </p>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center bg-forest/5 p-3 rounded-lg border-l-4 border-forest">
                <span><strong>Step 1 — Collect Expert-Verified Samples</strong></span>
                <span className="font-bold text-forest">✓ COMPLETED</span>
              </div>
              <div className="flex justify-between items-center bg-forest/5 p-3 rounded-lg border-l-4 border-forest">
                <span><strong>Step 2 — Validate Labels and Images</strong></span>
                <span className="font-bold text-forest">✓ COMPLETED</span>
              </div>
              <div className="flex justify-between items-center bg-forest/5 p-3 rounded-lg border-l-4 border-forest">
                <span><strong>Step 3 — Create Active Learning Batch</strong></span>
                <span className="font-bold text-forest">✓ COMPLETED</span>
              </div>
              <div
                className="flex justify-between items-center p-3 rounded-lg border-l-4"
                style={{
                  background: selectedBatch.batch.export_count > 0 ? '#f0fff4' : '#fffaf0',
                  borderLeftColor: selectedBatch.batch.export_count > 0 ? '#38a169' : '#d9a521',
                }}
              >
                <span><strong>Step 4 — Export Batch for Offline Retraining</strong></span>
                <span className="font-bold" style={{ color: selectedBatch.batch.export_count > 0 ? '#2f855a' : '#d9a521' }}>
                  {selectedBatch.batch.export_count > 0 ? '✓ EXPORTED' : 'READY'}
                </span>
              </div>
              <div className="flex justify-between items-center bg-beige/10 p-3 rounded-lg border-l-4 border-beige/60">
                <span><strong>Step 5 — Candidate Model Retraining</strong></span>
                <span className="text-forest-muted font-semibold">OFFLINE — NOT EXECUTED BY WEB APP</span>
              </div>
              <div className="flex justify-between items-center bg-beige/10 p-3 rounded-lg border-l-4 border-beige/60">
                <span><strong>Step 6 — Held-Out Evaluation & Candidate Comparison</strong></span>
                <span className="text-forest-muted font-semibold">OFFLINE — REQUIRES CANDIDATE MODEL</span>
              </div>
              <div className="flex justify-between items-center bg-beige/10 p-3 rounded-lg border-l-4 border-beige/60">
                <span><strong>Step 7 — Deployment Approval</strong></span>
                <span className="text-forest-light font-bold">WAITING</span>
              </div>
            </div>
          </div>
        </div>
            )}

            {/* Candidate Upload (manual .pth generated externally in Colab) */}
            <div className="rounded-xl border border-beige bg-beige/10 p-5 space-y-4">
              <h3 className="font-bold text-forest text-sm flex items-center gap-1">
                <UploadCloud className="h-4 w-4 text-amber" /> Upload Evaluated Checkpoint
              </h3>
              <p className="text-xs text-forest-muted">
                Upload the .pth candidate checkpoint generated in Google Colab, together with its held-out evaluation metrics, so it can be compared against the current deployed model.
              </p>
              {uploadError && <div className="rounded-lg bg-red-50 text-red-700 p-2.5 text-xs font-semibold">{uploadError}</div>}
              {uploadSuccess && <div className="rounded-lg bg-green-50 text-green-700 p-2.5 text-xs font-semibold">{uploadSuccess}</div>}

              <form onSubmit={handleUploadSubmit} className="space-y-3">
              <div>
                <label className="text-xs font-semibold block mb-1">Candidate file (.pth)</label>
                <input
                  id="candidate-file-input"
                  type="file"
                  accept=".pth"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="bg-white border border-beige"
                  style={{ padding: '8px' }}
                />
              </div>

              <div className="grid gap-3 grid-cols-2">
                <div>
                  <label className="text-xs font-semibold block mb-1">Test Accuracy (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="e.g. 96.66"
                    value={testAccuracy}
                    onChange={(e) => setTestAccuracy(e.target.value)}
                    style={{ padding: '8px' }}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold block mb-1">Macro F1</label>
                  <input
                    type="number"
                    step="0.0001"
                    placeholder="e.g. 0.9665"
                    value={macroF1}
                    onChange={(e) => setMacroF1(e.target.value)}
                    style={{ padding: '8px' }}
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold block mb-1">Source Batch ID</label>
                <input
                  type="text"
                  placeholder="e.g. AL-BATCH-..."
                  value={sourceBatchId}
                  onChange={(e) => setSourceBatchId(e.target.value)}
                  style={{ padding: '8px' }}
                />
              </div>

              <div>
                <label className="text-xs font-semibold block mb-1">Notes</label>
                <textarea
                  placeholder="Notes on retrained candidate..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  style={{ padding: '8px', height: '60px' }}
                />
              </div>

              <button
                type="submit"
                disabled={isUploading}
                className="primary-submit-btn w-full mt-2"
              >
                {isUploading ? 'Uploading Checkpoint...' : 'Upload & Validate'}
              </button>
            </form>
          </div>
          </div>
        ) : (
          <div className="space-y-6 animate-entrance">
            <div className="rounded-xl border border-beige bg-beige/10 p-5 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <span className="eyebrow">Option 2</span>
                  <h3 className="font-bold text-forest text-base" style={{ margin: 0 }}>In-App PyTorch Fine-Tuning</h3>
                </div>
                <span className="analytics-panel__badge">Integrated / In-App Workflow</span>
              </div>
              <p className="text-sm text-forest-muted">
                Use expert-verified samples to fine-tune the currently deployed model directly inside PaddyGuard using real PyTorch. A new candidate checkpoint is automatically created, evaluated on the held-out test set, and compared with the current deployed model.
              </p>
              <p className="text-xs text-forest-muted italic">
                Best for demonstrating the complete automated human-in-the-loop model update pipeline.
              </p>
              <div className="flex flex-wrap items-center gap-2 pt-2 text-xs font-semibold text-forest">
                {[
                  'Expert Verified Samples',
                  'Readiness Check',
                  'Start Fine-Tuning',
                  'Real PyTorch Training',
                  'Automatic Candidate Creation',
                  'Held-out Evaluation',
                  'Current vs Candidate Comparison',
                  'Reject / Eligible for Promotion',
                ].map((step, i, arr) => (
                  <span key={step} className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-full bg-white border border-beige">{step}</span>
                    {i < arr.length - 1 && <span className="text-forest-muted">&rarr;</span>}
                  </span>
                ))}
              </div>
            </div>

            {/* 3b. In-App Fine Tuning (Real PyTorch) — existing component, unmodified */}
            <FineTuningPanel />
          </div>
        )}
      </section>

      {/* 2. Candidate Evaluation & Model Governance (shared by both workflows) — collapsible */}
      <section className="card space-y-0" ref={governanceRef}>
        <button
          type="button"
          onClick={() => setGovernanceExpanded((v) => !v)}
          aria-expanded={governanceExpanded}
          className="w-full flex items-center justify-between gap-3 text-left"
          style={{ background: 'none', border: 0, padding: 0, margin: 0, cursor: 'pointer' }}
        >
          <div>
            <h2 className="text-xl font-bold text-forest mb-1" style={{ margin: 0 }}>Candidate Evaluation &amp; Model Governance</h2>
            {!governanceExpanded && (
              <div className="text-xs text-forest-muted space-y-0.5 mt-1">
                <p style={{ margin: 0 }}>
                  Current Model: {deployedModel?.test_accuracy ? `${(deployedModel.test_accuracy * 100).toFixed(2)}%` : '97.14%'} Accuracy | F1 {deployedModel?.macro_f1 ? deployedModel.macro_f1.toFixed(4) : '0.9714'}
                </p>
                <p style={{ margin: 0 }}>
                  {candidates.length} Previous Candidate{candidates.length === 1 ? '' : 's'}
                </p>
              </div>
            )}
          </div>
          <ChevronDown
            className={`h-5 w-5 text-forest flex-shrink-0 transition-transform duration-200 ${governanceExpanded ? 'rotate-180' : ''}`}
          />
        </button>

        {governanceExpanded && (
          <div className="space-y-6 animate-entrance pt-6">
            <p className="text-xs text-forest-muted">
              Candidates produced by either workflow — Option 1 offline/Colab uploads or Option 2 in-app PyTorch training — pass through this same held-out evaluation and promotion-decision process before any deployment change is made.
            </p>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-xl border border-beige p-4 bg-beige/10 space-y-2">
                <h3 className="font-bold text-forest text-sm">Current Deployed Model</h3>
                <div className="text-sm text-forest space-y-1">
                  <p><strong>Checkpoint:</strong> {deployedModel?.checkpoint || 'PaddyGuard_active_learning_round2.pth'}</p>
                  <p><strong>Test Accuracy:</strong> {deployedModel?.test_accuracy ? `${(deployedModel.test_accuracy * 100).toFixed(2)}%` : '97.14%'}</p>
                  <p><strong>Macro F1:</strong> {deployedModel?.macro_f1 ? deployedModel.macro_f1.toFixed(4) : '0.9714'}</p>
                </div>
                <p className="text-[11px] text-forest-muted pt-2 border-t border-beige/60">
                  Every candidate — regardless of which fine-tuning workflow produced it — is compared against this checkpoint before a promotion decision is made.
                </p>
              </div>

              {/* Model Comparison Graph */}
              <div className="rounded-xl border border-beige bg-white p-5 space-y-4">
            <h3 className="font-bold text-forest text-sm">Model Comparison</h3>
            {selectedCandidate ? (
              <div className="space-y-4">
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[
                        {
                          name: 'Accuracy (%)',
                          Current: (deployedModel?.test_accuracy || 0.9714) * 100,
                          Candidate: selectedCandidate.test_accuracy * 100,
                        },
                        {
                          name: 'Macro F1 (x100)',
                          Current: (deployedModel?.macro_f1 || 0.9714) * 100,
                          Candidate: selectedCandidate.macro_f1 * 100,
                        },
                      ]}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" tick={{ fill: '#4a5568', fontSize: 10 }} />
                      <YAxis domain={[90, 100]} allowDecimals={false} tick={{ fill: '#4a5568', fontSize: 10 }} />
                      <Tooltip
                        formatter={(value) => {
                          const numericValue = Array.isArray(value) ? Number(value[0]) : Number(value);
                          return Number.isFinite(numericValue) ? numericValue.toFixed(2) : String(value ?? '');
                        }}
                      />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: '11px' }} />
                      <Bar dataKey="Current" fill="#a0aec0" barSize={25} />
                      <Bar
                        dataKey="Candidate"
                        fill={selectedCandidate.status === 'ELIGIBLE_FOR_REVIEW' ? '#38a169' : '#e53e3e'}
                        barSize={25}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-beige/10 rounded-lg p-3 text-xs text-forest space-y-1.5 border border-beige/60">
                  <h4 className="font-bold text-forest-muted">Performance Deltas</h4>
                  <p>
                    Accuracy Change:{' '}
                    <span
                      className={
                        selectedCandidate.test_accuracy - (deployedModel?.test_accuracy || 0.9714) > 0
                          ? 'text-forest font-bold'
                          : 'text-red font-bold'
                      }
                    >
                      {selectedCandidate.test_accuracy - (deployedModel?.test_accuracy || 0.9714) > 0 ? '+' : ''}
                      {((selectedCandidate.test_accuracy - (deployedModel?.test_accuracy || 0.9714)) * 100).toFixed(2)}{' '}
                      pp
                    </span>
                  </p>
                  <p>
                    Macro F1 Change:{' '}
                    <span
                      className={
                        selectedCandidate.macro_f1 - (deployedModel?.macro_f1 || 0.9714) >= 0
                          ? 'text-forest font-bold'
                          : 'text-red font-bold'
                      }
                    >
                      {selectedCandidate.macro_f1 - (deployedModel?.macro_f1 || 0.9714) >= 0 ? '+' : ''}
                      {(selectedCandidate.macro_f1 - (deployedModel?.macro_f1 || 0.9714)).toFixed(4)}
                    </span>
                  </p>
                </div>

                <div
                  className="rounded-lg p-3 border text-xs"
                  style={{
                    background: selectedCandidate.status === 'ELIGIBLE_FOR_REVIEW' ? '#f0fff4' : '#fff5f5',
                    borderColor: selectedCandidate.status === 'ELIGIBLE_FOR_REVIEW' ? '#c6f6d5' : '#fed7d7',
                    color: selectedCandidate.status === 'ELIGIBLE_FOR_REVIEW' ? '#2f855a' : '#c53030',
                  }}
                >
                  <strong className="block text-sm">
                    {selectedCandidate.status === 'ELIGIBLE_FOR_REVIEW' ? 'ELIGIBLE FOR DEPLOYMENT REVIEW' : 'CANDIDATE REJECTED'}
                  </strong>
                  <span className="block mt-0.5">
                    {selectedCandidate.status === 'ELIGIBLE_FOR_REVIEW'
                      ? 'Candidate Outperformed Current Model'
                      : 'Keep Current Round 2 Model'}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-forest-muted italic py-6">No candidate model loaded.</p>
            )}
          </div>
        </div>

        {/* Previous Candidates table */}
        {candidates.length > 0 && (
          <div className="space-y-3 pt-3 border-t border-beige/60">
            <h3 className="font-bold text-forest text-sm">Previously Uploaded Candidates</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Uploaded At</th>
                    <th>Filename</th>
                    <th>Accuracy</th>
                    <th>Macro F1</th>
                    <th>Accuracy Delta</th>
                    <th>F1 Delta</th>
                    <th>Source Batch</th>
                    <th>Decision</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => {
                    const baselineAcc = deployedModel?.test_accuracy || 0.9714
                    const baselineF1 = deployedModel?.macro_f1 || 0.9714
                    const accDelta = (c.test_accuracy - baselineAcc) * 100
                    const f1Delta = c.macro_f1 - baselineF1
                    return (
                      <tr key={c.candidate_id} style={{ background: selectedCandidate?.candidate_id === c.candidate_id ? '#f4fbf6' : 'none' }}>
                        <td className="text-xs text-forest-muted">{new Date(c.uploaded_at).toLocaleString()}</td>
                        <td className="font-mono text-xs text-forest-light">
                          {c.checkpoint_pruned_at ? (
                            <span className="text-xs text-forest-muted">Pruned checkpoint</span>
                          ) : (
                            c.filename
                          )}
                        </td>
                        <td className="text-xs text-forest">{(c.test_accuracy * 100).toFixed(2)}%</td>
                        <td className="text-xs text-forest">{c.macro_f1.toFixed(4)}</td>
                        <td className={accDelta > 0 ? 'text-forest font-bold text-xs' : 'text-red text-xs'}>
                          {accDelta > 0 ? '+' : ''}
                          {accDelta.toFixed(2)} pp
                        </td>
                        <td className={f1Delta >= 0 ? 'text-forest font-bold text-xs' : 'text-red text-xs'}>
                          {f1Delta >= 0 ? '+' : ''}
                          {f1Delta.toFixed(4)}
                        </td>
                        <td className="text-xs text-forest-muted">{c.source_batch_id || 'N/A'}</td>
                        <td>
                          <span
                            className="px-2 py-0.5 rounded text-[10px] font-bold"
                            style={{
                              background: c.status === 'ELIGIBLE_FOR_REVIEW' ? '#c6f6d5' : '#fed7d7',
                              color: c.status === 'ELIGIBLE_FOR_REVIEW' ? '#22543d' : '#742a2a',
                            }}
                          >
                            {c.status === 'ELIGIBLE_FOR_REVIEW' ? 'Review Eligible' : 'Rejected'}
                          </span>
                        </td>
                        <td className="text-right">
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => openCandidateComparison(c)}
                              className="primary-btn text-xs py-1 px-2.5 rounded-lg"
                              style={{ width: 'auto', padding: '4px 10px', fontSize: '0.8rem' }}
                            >
                              Compare
                            </button>
                            {canDeleteLeafRecords && (
                              <button
                                onClick={() => setCandidateToDelete(c)}
                                className="bg-red-500 hover:bg-red-600 text-white text-xs py-1 px-2.5 rounded-lg"
                                style={{ width: 'auto', padding: '4px 10px', fontSize: '0.8rem' }}
                              >
                                Delete
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
          </div>
        )}
      </section>

      {/* 3. Research Experiment Results — controlled/offline research evidence, collapsible, kept separate from live in-app fine-tuning data */}
      <section className="card space-y-0">
        <button
          type="button"
          onClick={() => setResearchExpanded((v) => !v)}
          aria-expanded={researchExpanded}
          className="w-full flex items-center justify-between gap-3 text-left"
          style={{ background: 'none', border: 0, padding: 0, margin: 0, cursor: 'pointer' }}
        >
          <div>
            <h2 className="text-xl font-bold text-forest mb-1" style={{ margin: 0 }}>Research Experiment Results</h2>
            {!researchExpanded && (
              <p className="text-xs text-forest-muted" style={{ margin: '4px 0 0' }}>
                Best: Active Learning Round 2 | {deployedModel?.test_accuracy ? `${(deployedModel.test_accuracy * 100).toFixed(2)}%` : '97.14%'} Accuracy | F1 {deployedModel?.macro_f1 ? deployedModel.macro_f1.toFixed(4) : '0.9714'} | AL vs Random +0.48 pp
              </p>
            )}
          </div>
          <ChevronDown
            className={`h-5 w-5 text-forest flex-shrink-0 transition-transform duration-200 ${researchExpanded ? 'rotate-180' : ''}`}
          />
        </button>

        {researchExpanded && (
          <div className="space-y-6 animate-entrance pt-6">
            <p className="text-sm text-forest-muted">
              Research dashboard — shows controlled Active Learning experiment results and live verified samples collected for future retraining.
            </p>

            <div className="rounded-xl border border-forest/10 bg-forest/5 p-4 text-xs space-y-1">
              <p className="text-forest font-semibold">
                Selection Policy:
              </p>
              <p className="text-forest-muted">
                Expert review candidates are selected using a hybrid uncertainty strategy: all valid predictions below 50% confidence plus the five lowest-confidence pending predictions. Model retraining is performed offline in controlled experiments. Expert verification does not automatically update the deployed model.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-xl border border-beige p-4 bg-beige/10 space-y-2">
                <h3 className="font-bold text-forest text-sm">Current Deployed Model</h3>
                <div className="text-sm text-forest space-y-1">
                  <p><strong>Checkpoint:</strong> {deployedModel?.checkpoint || 'PaddyGuard_active_learning_round2.pth'}</p>
                  <p><strong>Architecture:</strong> EfficientNetB3</p>
                  <p><strong>Test Accuracy:</strong> {deployedModel?.test_accuracy ? `${(deployedModel.test_accuracy * 100).toFixed(2)}%` : '97.14%'}</p>
                  <p><strong>Macro F1:</strong> {deployedModel?.macro_f1 ? deployedModel.macro_f1.toFixed(4) : '0.9714'}</p>
                  <p><strong>Training labels:</strong> 2300</p>
                  <p><strong>Classes:</strong> 4</p>
                </div>
                <p className="text-[11px] text-forest-muted pt-2 border-t border-beige/60">
                  The deployed checkpoint was selected from the Active Learning experiment because Round 2 achieved the highest held-out test performance.
                </p>
              </div>

              <div className="rounded-xl border border-beige p-4 bg-white space-y-2">
                <h3 className="font-bold text-forest text-sm">Key Findings</h3>
                <div className="text-sm text-forest space-y-1">
                  <p><strong>Same annotation budget (2300 labels):</strong></p>
                  <ul className="list-disc pl-5 text-xs text-forest-muted space-y-0.5">
                    <li>Active Learning: 97.14%</li>
                    <li>Random Sampling: 96.66%</li>
                  </ul>
                  <p>Difference: <strong>+0.48</strong> percentage points in this experiment.</p>
                  <p className="pt-2 border-t border-beige/60"><strong>Overall Improvement:</strong></p>
                  <p className="text-xs">Baseline (95.70%) → Best Active Learning (97.14%) (+1.44 percentage points)</p>
                </div>
              </div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Experiment Phase</th>
                    <th>Labels</th>
                    <th>Accuracy</th>
                    <th>Macro F1</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Baseline</td>
                    <td>2100</td>
                    <td>95.70%</td>
                    <td>0.9568</td>
                  </tr>
                  <tr>
                    <td>Active Learning +100</td>
                    <td>2200</td>
                    <td>96.90%</td>
                    <td>0.9689</td>
                  </tr>
                  <tr>
                    <td>Random +100</td>
                    <td>2200</td>
                    <td>96.54%</td>
                    <td>0.9652</td>
                  </tr>
                  <tr style={{ background: '#f0fff4', fontWeight: 'bold' }}>
                    <td>Active Learning +200 (Deployed)</td>
                    <td>2300</td>
                    <td>97.14%</td>
                    <td>0.9714</td>
                  </tr>
                  <tr>
                    <td>Random +200</td>
                    <td>2300</td>
                    <td>96.66%</td>
                    <td>0.9664</td>
                  </tr>
                  <tr>
                    <td>Active Learning +300</td>
                    <td>2400</td>
                    <td>96.90%</td>
                    <td>0.9690</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* 4. Live Active Learning Data */}
      <section className="card space-y-6">
        <div>
          <h2 className="text-xl font-bold text-forest mb-1" style={{ margin: 0 }}>Live Active Learning Data</h2>
          <p className="text-xs text-forest-muted">
            Telemetry metrics of the live expert review process.
          </p>
        </div>

        {error && <p className="error">{error}</p>}
        {stats && (
          <div className="space-y-6">
            <div className="grid gap-4 grid-cols-2 md:grid-cols-5">
              <div className="rounded-xl border border-beige bg-beige/10 p-3">
                <span className="text-[10px] text-forest-muted uppercase tracking-wider block">Pending Reviews</span>
                <strong className="text-2xl text-forest block mt-1">{stats.pending_expert_reviews}</strong>
              </div>
              <div className="rounded-xl border border-beige bg-beige/10 p-3">
                <span className="text-[10px] text-forest-muted uppercase tracking-wider block">Verified Samples</span>
                <strong className="text-2xl text-forest block mt-1">{stats.verified_expert_samples}</strong>
              </div>
              <div className="rounded-xl border border-beige bg-beige/10 p-3">
                <span className="text-[10px] text-forest-muted uppercase tracking-wider block">Approved for Training</span>
                <strong className="text-2xl text-forest block mt-1">{stats.approved_for_training_samples}</strong>
              </div>
              <div className="rounded-xl border border-beige bg-beige/10 p-3">
                <span className="text-[10px] text-forest-muted uppercase tracking-wider block">Available / Unused</span>
                <strong className="text-2xl text-forest block mt-1">{stats.active_learning_eligible_samples}</strong>
              </div>
              <div className="rounded-xl border border-beige bg-beige/10 p-3">
                <span className="text-[10px] text-forest-muted uppercase tracking-wider block">Consumed / Used</span>
                <strong className="text-2xl text-forest block mt-1">{stats.consumed_training_samples}</strong>
              </div>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[
                    { name: 'Pending Review', count: stats.pending_expert_reviews },
                    { name: 'Verified', count: stats.verified_expert_samples },
                    { name: 'Approved', count: stats.approved_for_training_samples },
                    { name: 'Available', count: stats.active_learning_eligible_samples },
                    { name: 'Consumed', count: stats.consumed_training_samples },
                    { name: 'Active Models', count: stats.storage_summary?.active_models || 0 },
                    { name: 'Backups Kept', count: stats.storage_summary?.backups_kept || 0 },
                    { name: 'Rejected Kept', count: stats.storage_summary?.rejected_candidates_kept || 0 },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#4a5568', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fill: '#4a5568', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#f4f8f5' }} contentStyle={{ borderRadius: '8px', border: '1px solid #dfece3' }} />
                  <Bar dataKey="count" fill="#2c7a7b" radius={[4, 4, 0, 0]} barSize={35} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </section>

      {/* Demo batch Warning Modal */}
      {compareCandidate && (
        <Modal isOpen={Boolean(compareCandidate)} onClose={() => setCompareCandidate(null)} title="Candidate Comparison" size="lg">
          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-beige bg-beige/10 p-4">
                <h4 className="font-bold text-forest text-sm mb-2">Current Model</h4>
                <p className="text-xs text-forest-muted"><strong>Checkpoint:</strong> {deployedModel?.checkpoint || 'PaddyGuard_active_learning_round2.pth'}</p>
                <p className="text-xs text-forest-muted"><strong>Accuracy:</strong> {((deployedModel?.test_accuracy || 0.9714) * 100).toFixed(2)}%</p>
                <p className="text-xs text-forest-muted"><strong>Macro F1:</strong> {(deployedModel?.macro_f1 || 0.9714).toFixed(4)}</p>
              </div>
              <div className="rounded-xl border border-beige bg-beige/10 p-4">
                <h4 className="font-bold text-forest text-sm mb-2">Candidate Model</h4>
                <p className="text-xs text-forest-muted"><strong>Filename:</strong> {compareCandidate.filename}</p>
                <p className="text-xs text-forest-muted"><strong>Accuracy:</strong> {(compareCandidate.test_accuracy * 100).toFixed(2)}%</p>
                <p className="text-xs text-forest-muted"><strong>Macro F1:</strong> {compareCandidate.macro_f1.toFixed(4)}</p>
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-beige">
              <table className="w-full text-left">
                <thead className="bg-beige/40">
                  <tr>
                    <th className="p-3 text-xs uppercase text-forest-muted">Metric</th>
                    <th className="p-3 text-xs uppercase text-forest-muted">Current Model</th>
                    <th className="p-3 text-xs uppercase text-forest-muted">Candidate</th>
                    <th className="p-3 text-xs uppercase text-forest-muted">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    {
                      label: 'Accuracy',
                      current: (deployedModel?.test_accuracy || 0.9714) * 100,
                      candidate: compareCandidate.test_accuracy * 100,
                      delta: (compareCandidate.test_accuracy - (deployedModel?.test_accuracy || 0.9714)) * 100,
                      suffix: '%',
                    },
                    {
                      label: 'Macro F1',
                      current: (deployedModel?.macro_f1 || 0.9714) * 100,
                      candidate: compareCandidate.macro_f1 * 100,
                      delta: (compareCandidate.macro_f1 - (deployedModel?.macro_f1 || 0.9714)) * 100,
                      suffix: '%',
                    },
                  ].map((row) => (
                    <tr key={row.label} className="border-t border-beige">
                      <td className="p-3 text-sm font-semibold text-forest">{row.label}</td>
                      <td className="p-3 text-sm text-forest-muted">{row.current.toFixed(2)}{row.suffix}</td>
                      <td className="p-3 text-sm text-forest-muted">{row.candidate.toFixed(2)}{row.suffix}</td>
                      <td className={`p-3 text-sm font-bold ${row.delta >= 0 ? 'text-forest' : 'text-red-600'}`}>
                        {row.delta >= 0 ? '+' : ''}{row.delta.toFixed(2)} pp
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid gap-3 md:grid-cols-2 text-xs text-forest-muted">
              <div><strong>Source Batch:</strong> {compareCandidate.source_batch_id || 'N/A'}</div>
              <div><strong>Upload Date:</strong> {new Date(compareCandidate.uploaded_at).toLocaleString()}</div>
              <div><strong>Decision:</strong> {compareCandidate.status === 'ELIGIBLE_FOR_REVIEW' ? 'Review Eligible' : 'Rejected'}</div>
              <div><strong>Status:</strong> {compareCandidate.status}</div>
            </div>

            <div className="flex justify-end">
              <button onClick={() => setCompareCandidate(null)} className="primary-btn text-sm py-2 px-4 rounded-lg">
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}

      <ConfirmDialog
        isOpen={Boolean(candidateToDelete)}
        title="Delete candidate model"
        message={`Are you sure you want to delete this candidate model?\n\nFilename: ${candidateToDelete?.filename ?? 'Unknown'}\nUpload date: ${candidateToDelete?.uploaded_at ? new Date(candidateToDelete.uploaded_at).toLocaleString() : 'N/A'}\nDecision: ${candidateToDelete?.status === 'ELIGIBLE_FOR_REVIEW' ? 'Review Eligible' : 'Rejected'}\nSource batch: ${candidateToDelete?.source_batch_id || 'N/A'}`}
        confirmLabel="Delete Candidate"
        danger
        loading={candidateDeleteLoading}
        onConfirm={confirmCandidateDelete}
        onCancel={() => setCandidateToDelete(null)}
      />

      <ConfirmDialog
        isOpen={Boolean(batchToDelete)}
        title="Delete Active Learning batch"
        message={`Delete Active Learning batch ${batchToDelete?.batch_id ?? 'Unknown'}?\n\nCreated: ${batchToDelete?.created_at ? new Date(batchToDelete.created_at).toLocaleString() : 'N/A'}\nSamples: ${batchToDelete?.sample_count ?? 0}\nStatus: ${batchToDelete?.status ?? 'UNKNOWN'}\nMode: ${batchToDelete?.is_demo_mode ? 'DEMO' : 'RESEARCH'}`}
        confirmLabel="Delete Batch"
        danger
        loading={batchDeleteLoading}
        onConfirm={confirmBatchDelete}
        onCancel={() => setBatchToDelete(null)}
      />

      {warningModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', maxWidth: '500px' }}>
            <h3 style={{ color: '#dd6b20', marginBottom: '1rem', fontWeight: 'bold' }}>Demo Batch Warning</h3>
            <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#4a5568' }}>
              This batch contains fewer than the recommended 100 expert-verified samples.
            </p>
            <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#4a5568' }}>
              The controlled PaddyGuard Active Learning experiments used 100 newly labelled samples per round.
            </p>
            <p style={{ marginBottom: '1.5rem', padding: '1rem', background: '#fffaf0', borderRadius: '4px', fontSize: '0.85rem', color: '#b45309' }}>
              You may continue for demonstration purposes, but this batch is not equivalent to a new controlled research round.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setWarningModalOpen(false)}
                className="btn-secondary"
                style={{ width: 'auto', padding: '8px 16px' }}
              >
                Cancel
              </button>
              <button
                onClick={executePrepare}
                disabled={isPreparingBatch}
                className="primary-submit-btn"
                style={{ width: 'auto', padding: '8px 16px', background: '#dd6b20' }}
              >
                {isPreparingBatch ? 'Preparing...' : 'Prepare Demo Batch'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
