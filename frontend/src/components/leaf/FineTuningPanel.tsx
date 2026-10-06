import { useEffect, useState, useRef } from 'react'
import { checkFineTuneReadiness, startFineTuning, getFineTuneJobs, getFineTuneJobStatus, promoteCandidate, getDeployedModel } from '@/lib/leafApi'
import type { FineTuneReadiness, FineTuneJob, FineTuneJobStatus } from '@/lib/leafApi'


export default function FineTuningPanel() {
  const [readiness, setReadiness] = useState<FineTuneReadiness | null>(null)
  const [jobs, setJobs] = useState<FineTuneJob[]>([])
  const [deployedModel, setDeployedModel] = useState<any>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isStartingTraining, setIsStartingTraining] = useState(false)
  const [activeJob, setActiveJob] = useState<FineTuneJobStatus | null>(null)
  const [isDeployingJobId, setIsDeployingJobId] = useState<string | null>(null)
  const pollInterval = useRef<any>(null)
  const pollErrorCount = useRef(0)

  useEffect(() => {
    loadInitialData()
    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current)
    }
  }, [])

  async function loadInitialData() {
    try {
      const read = await checkFineTuneReadiness()
      setReadiness(read)
      
      const jobsList = await getFineTuneJobs()
      setJobs(jobsList)
      
      const active = jobsList.find((j) => j.status !== 'COMPLETED' && j.status !== 'FAILED' && j.status !== 'PROMOTED')
      if (active) {
        startPolling(active.job_id)
      }

      const deployed = await getDeployedModel()
      setDeployedModel(deployed)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to check fine-tuning status.')
    }
  }

  function startPolling(jobId: string) {
    pollErrorCount.current = 0
    fetchJobStatus(jobId)
    if (pollInterval.current) clearInterval(pollInterval.current)
    pollInterval.current = setInterval(() => {
      fetchJobStatus(jobId)
    }, 2000)
  }

  async function fetchJobStatus(jobId: string) {
    try {
      const status = await getFineTuneJobStatus(jobId)
      pollErrorCount.current = 0
      setActiveJob(status)
      if (['COMPLETED', 'FAILED', 'PROMOTED'].includes(status.status)) {
        if (pollInterval.current) clearInterval(pollInterval.current)
        loadInitialData() // refresh lists
      }
    } catch (err) {
      pollErrorCount.current += 1
      if (pollErrorCount.current >= 5) {
        console.warn('Stopped polling fine-tune job status after 5 consecutive errors')
        if (pollInterval.current) clearInterval(pollInterval.current)
      }
    }
  }

  async function handleStart() {
    setError('')
    setSuccess('')
    setIsStartingTraining(true)
    try {
      const res = await startFineTuning()
      setSuccess('Training started!')
      startPolling(res.job_id)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to start fine-tuning.')
    } finally {
      setIsStartingTraining(false)
    }
  }

  async function handlePromote(jobId: string) {
    setError('')
    setSuccess('')
    setIsDeployingJobId(jobId)
    try {
      await promoteCandidate(jobId)
      setSuccess('Model promoted successfully!')
      loadInitialData()
    } catch (err: any) {
      // If endpoint is missing or returns 404
      if (err.response?.status === 404) {
        setError('Promotion API route is not declared on the Gateway. Deployed checkpoint remains ' + (deployedModel?.checkpoint || 'active_learning_round2.pth'))
      } else {
        setError(err.response?.data?.detail || err.message || 'Failed to promote candidate.')
      }
    } finally {
      setIsDeployingJobId(null)
    }
  }

  return (
    <div className="card space-y-6">
      <div>
        <h2 className="text-xl font-bold text-forest mb-1" style={{ margin: 0 }}>In-App Fine-Tuning (Real PyTorch)</h2>
        <p className="text-xs text-forest-muted">
          Agricultural admin portal: retrain your classifier models using live verified crop data directly.
        </p>
      </div>
      
      {error && <div className="rounded-xl bg-red-50 border border-red-200 text-red-700 p-3.5 text-sm">{error}</div>}
      {success && <div className="rounded-xl bg-green-50 border border-green-200 text-green-700 p-3.5 text-sm">{success}</div>}

      <div className="grid gap-6 md:grid-cols-2">
        <div className="border border-beige rounded-xl p-4 bg-beige/10 space-y-4">
          <h3 className="font-bold text-forest text-sm">Readiness Check</h3>
          {readiness ? (
            <div className="space-y-3">
              <ul className="list-disc pl-5 text-sm text-forest space-y-1">
                <li>Verified Samples: <strong>{readiness.eligible_new_samples}</strong> / {readiness.min_required}</li>
                <li>Test Dataset Ready: <strong>{readiness.test_dataset_ready ? 'Yes' : 'No'}</strong></li>
                {!readiness.can_train && (
                  <li className="text-red font-bold mt-2">
                    Blockers:
                    <ul className="list-disc pl-5 font-normal text-xs text-forest-muted mt-1 space-y-1">
                      {readiness.blockers.map((b, i) => <li key={i}>{b}</li>)}
                    </ul>
                  </li>
                )}
              </ul>
              
              <button
                onClick={handleStart}
                disabled={!readiness?.can_train || activeJob !== null || isStartingTraining}
                className="primary-submit-btn w-full mt-2"
              >
                {isStartingTraining ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="button-spinner" /> Starting Fine-Tuning...
                  </span>
                ) : activeJob ? (
                  'Training in Progress...'
                ) : (
                  'Start Fine-Tuning'
                )}
              </button>
            </div>
          ) : (
            <p className="text-xs text-forest-muted">Loading readiness stats...</p>
          )}
        </div>

        <div className="border border-beige rounded-xl p-4 bg-white space-y-3">
          <h3 className="font-bold text-forest text-sm">Active Deployed Model</h3>
          {deployedModel ? (
            <div className="space-y-2 text-sm text-forest">
              <p><span className="text-forest-muted text-xs block">Checkpoint</span> <strong>{deployedModel.checkpoint}</strong></p>
              <p><span className="text-forest-muted text-xs block">Test Accuracy</span> <strong>{(deployedModel.test_accuracy * 100).toFixed(2)}%</strong></p>
              <p><span className="text-forest-muted text-xs block">Macro F1</span> <strong>{deployedModel.macro_f1.toFixed(4)}</strong></p>
              <p><span className="text-forest-muted text-xs block">Notes</span> <span className="text-xs text-forest-light">{deployedModel.notes || 'No notes'}</span></p>
              <p><span className="text-forest-muted text-xs block">Deployed At</span> <span className="text-xs text-forest-light">{deployedModel.deployed_at ? new Date(deployedModel.deployed_at).toLocaleString() : 'N/A'}</span></p>
            </div>
          ) : (
            <p className="text-xs text-forest-muted">Loading active checkpoint metrics...</p>
          )}
        </div>
      </div>

      {activeJob && (
        <div className="border border-forest/20 bg-forest/5 p-4 rounded-xl space-y-2">
          <h3 className="font-bold text-forest text-sm">Active Training Job: {activeJob.job_id}</h3>
          <p className="text-xs text-forest"><strong>Status:</strong> {activeJob.status}</p>
          <p className="text-xs text-forest"><strong>Progress:</strong> Epoch {activeJob.epochs_completed} / {activeJob.total_epochs}</p>
          {activeJob.log_tail && (
            <pre className="bg-forest-light/90 text-beige p-3 rounded-lg text-xs overflow-x-auto mt-2 font-mono" style={{ whiteSpace: 'pre-wrap', maxHeight: '180px' }}>
              {activeJob.log_tail}
            </pre>
          )}
        </div>
      )}

      <div>
        <h3 className="font-bold text-forest text-sm mb-3">Training History</h3>
        {jobs.length === 0 ? (
          <p className="text-sm text-forest-muted italic">No fine-tuning jobs run yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Samples</th>
                  <th>Acc / F1</th>
                  <th>Delta</th>
                  <th>Decision</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td className="font-mono text-xs text-forest-muted">{job.job_id.substring(0, 15)}...</td>
                    <td className="text-xs text-forest-muted">{job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}</td>
                    <td className="font-semibold text-xs text-forest">{job.status}</td>
                    <td className="text-xs text-forest">{job.source_sample_count}</td>
                    <td className="text-xs text-forest">
                      {job.candidate_accuracy ? `${(job.candidate_accuracy * 100).toFixed(1)}% / ${job.candidate_macro_f1?.toFixed(3)}` : '-'}
                    </td>
                    <td className="text-xs">
                      {job.accuracy_delta !== null ? (
                        <span className={job.accuracy_delta > 0 ? 'text-forest font-bold' : 'text-red'}>
                          {(job.accuracy_delta * 100).toFixed(2)}%
                        </span>
                      ) : '-'}
                    </td>
                    <td>
                      {job.decision === 'ELIGIBLE_FOR_PROMOTION' ? (
                        <span className="bg-green-100 text-forest px-2 py-0.5 rounded text-xs font-bold">ELIGIBLE</span>
                      ) : job.decision === 'REJECTED_BY_METRICS' ? (
                        <span className="bg-red-50 text-red px-2 py-0.5 rounded text-xs font-bold">REJECTED</span>
                      ) : job.decision === 'PROMOTED' ? (
                        <span className="bg-blue-50 text-blue-800 px-2 py-0.5 rounded text-xs font-bold">PROMOTED</span>
                      ) : '-'}
                    </td>
                    <td className="text-right">
                      {job.decision === 'ELIGIBLE_FOR_PROMOTION' && (
                        <button
                          onClick={() => handlePromote(job.job_id)}
                          disabled={isDeployingJobId !== null}
                          className="primary-btn text-xs py-1.5 px-3 rounded-lg"
                          style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
                        >
                          {isDeployingJobId === job.job_id ? 'Deploying...' : 'Deploy Now'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
