import axios from 'axios'

export interface LeafAuth {
  token: string
  username: string
  role: 'USER' | 'EXPERT' | 'SUPER_ADMIN'
  name: string
}

const LEAF_AUTH_KEY = 'paddyguard_leaf_auth'

export function getLeafAuth(): LeafAuth | null {
  const raw = localStorage.getItem(LEAF_AUTH_KEY)
  return raw ? (JSON.parse(raw) as LeafAuth) : null
}

export function setLeafAuth(auth: LeafAuth) {
  localStorage.setItem(LEAF_AUTH_KEY, JSON.stringify(auth))
}

export function clearLeafAuth() {
  localStorage.removeItem(LEAF_AUTH_KEY)
}

const leafApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 120000,
})

leafApi.interceptors.request.use((config) => {
  const auth = getLeafAuth()
  if (auth?.token) config.headers.Authorization = `Bearer ${auth.token}`
  return config
})

leafApi.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      clearLeafAuth()
    }
    return Promise.reject(error)
  }
)

const LEAF_API_BASE = '/api/v1/image'

/**
 * The leaf disease service (C2) keeps its own farmer accounts, separate from
 * user_management. Farmers who sign in through the main Login/Register flow
 * never see this — we transparently mirror their credentials into a leaf
 * session so /leaf history and analysis stay attributed to them. Best-effort:
 * failures here must never block the main login/register flow.
 */
export async function ensureLeafSession(email: string, password: string, fullName?: string): Promise<void> {
  try {
    const { data } = await leafApi.post(`${LEAF_API_BASE}/leaf-auth/login`, { username: email, password })
    setLeafAuth({ token: data.token, username: data.username, role: data.role, name: data.user?.name || data.username })
    return
  } catch {
    // Not yet registered on the leaf service — fall through to register+login.
  }
  try {
    await leafApi.post(`${LEAF_API_BASE}/leaf-auth/register`, {
      name: fullName || email.split('@')[0],
      email,
      password,
    })
    const { data } = await leafApi.post(`${LEAF_API_BASE}/leaf-auth/login`, { username: email, password })
    setLeafAuth({ token: data.token, username: data.username, role: data.role, name: data.user?.name || data.username })
  } catch {
    // Leaf service unavailable — /leaf features will prompt re-auth later.
  }
}

export async function staffLogin(username: string, password: string): Promise<LeafAuth> {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/leaf-auth/login`, { username, password })
  const auth: LeafAuth = { token: data.token, username: data.username, role: data.role, name: data.user?.name || data.username }
  setLeafAuth(auth)
  return auth
}

export interface LeafPrediction {
  status: 'KNOWN' | 'OOD' | 'UNCERTAIN'
  prediction: string
  confidence: number
  energy_score: number
  is_low_confidence: boolean
  needs_expert_review: boolean
  severity_percentage: number | null
  severity_method: string | null
  gradcam_base64: string | null
  class_probabilities: Record<string, number>
}

export interface AnalyzeResult {
  case_id: string
  prediction: LeafPrediction
  severity_level: string | null
  location: { city: string; district: string | null; latitude: number; longitude: number }
  weather: Record<string, unknown>
  yield_loss: Record<string, unknown> | null
  calculation_breakdown: Record<string, unknown> | null
  advisory: { message: string; safety: string }
  context_analysis?: null
}

export interface AnalyzeParams {
  file: File
  city?: string
  latitude?: number
  longitude?: number
  field_area_acres: number
  affected_field_percentage?: number
  rice_variety?: string
  growth_stage?: string
  created_by?: string
}

export async function analyzeLeaf(params: AnalyzeParams): Promise<AnalyzeResult> {
  const form = new FormData()
  form.append('image', params.file)
  form.append('field_area_acres', String(params.field_area_acres))
  if (params.city) form.append('city', params.city)
  if (params.latitude != null) form.append('latitude', String(params.latitude))
  if (params.longitude != null) form.append('longitude', String(params.longitude))
  form.append('affected_field_percentage', String(params.affected_field_percentage ?? 0))
  form.append('rice_variety', params.rice_variety || 'Unknown')
  form.append('growth_stage', params.growth_stage || 'Unknown')
  if (params.created_by) form.append('created_by', params.created_by)

  const { data } = await leafApi.post(`${LEAF_API_BASE}/classify`, form)
  return data
}

export interface CaseSummary {
  case_id: string
  created_at: string
  predicted_disease: string
  confidence: number
  severity_percentage: number | null
  severity_level: string | null
  city: string | null
  needs_expert_review: boolean
  review_status: string | null
  original_image_url: string | null
  gradcam_image_url: string | null
}

export async function getCases(username?: string): Promise<CaseSummary[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/cases`, { params: username ? { username } : {} })
  return data
}

export async function deleteCase(caseId: string): Promise<void> {
  await leafApi.delete(`${LEAF_API_BASE}/cases/${caseId}`)
}

export async function refreshWeather(caseId: string) {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/cases/${caseId}/refresh-weather`)
  return data
}

export async function getUserHistory(): Promise<CaseSummary[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/user/history`)
  return data
}

export interface ReviewQueueItem {
  case_id: string
  created_at: string
  predicted_disease: string
  confidence: number
  energy_score: number
  status: string
  review_status: string
  review_reason: string | null
  city: string | null
  original_image_url: string | null
  gradcam_image_url: string | null
}

export async function getReviewQueue(): Promise<ReviewQueueItem[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/review-queue`)
  return data
}

export async function verifyCase(caseId: string, expertLabel: string) {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert/review-queue/${caseId}/verify`, { expert_label: expertLabel })
  return data
}

export interface ClearPendingReviewQueueResult {
  success: boolean
  deleted_count: number
}

export async function clearPendingReviewQueue(): Promise<ClearPendingReviewQueueResult> {
  const { data } = await leafApi.delete(`${LEAF_API_BASE}/expert/review-queue/pending`)
  return data
}

export interface DashboardStats {
  pending_expert_reviews: number
  verified_expert_samples: number
  approved_for_training_samples: number
  active_learning_eligible_samples: number
  consumed_training_samples: number
  next_batch_size: number
  storage_summary: {
    active_models: number
    backups_kept: number
    max_backups: number
    rejected_candidates_kept: number
    max_rejected_candidates: number
  }
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/dashboard-stats`)
  return data
}

export interface Batch {
  batch_id: string
  created_at: string
  sample_count: number
  status: string
  is_demo_mode: boolean
  recommended_batch_size: number
}

export async function getBatches(): Promise<Batch[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/active-learning/batches`)
  return data
}

export async function prepareBatch(): Promise<Batch> {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert/active-learning/prepare-batch`)
  return data
}

export async function startBatch(batchId: string) {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert/active-learning/batches/${batchId}/start`)
  return data
}

export interface Expert {
  id: number
  name: string
  username: string
  role: string
  is_active: boolean
  created_at: string
  created_by: string | null
}

export async function getExperts(): Promise<Expert[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert-management`)
  return data
}

export async function createExpert(name: string, username: string, password: string) {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert-management`, { name, username, password })
  return data
}

export async function toggleExpert(id: number) {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert-management/${id}/toggle-status`)
  return data
}

export interface AdminUser {
  user_id: string
  name: string
  email: string
  role: string
  is_active: boolean
  created_at: string
  analysis_count: number
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/admin/users`)
  return data
}

// Active Learning & Fine-Tuning Additions
export interface CandidateModel {
  candidate_id: string
  filename: string
  test_accuracy: number
  macro_f1: number
  uploaded_at: string
  source_batch_id: string | null
  notes: string | null
  status: 'ELIGIBLE_FOR_REVIEW' | 'REJECTED'
  checkpoint_pruned_at: string | null
}

export interface FineTuneReadiness {
  can_train: boolean
  eligible_new_samples: number
  min_required: number
  test_dataset_ready: boolean
  blockers: string[]
}

export interface FineTuneJob {
  job_id: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PROMOTED'
  created_at: string
  source_sample_count: number
  candidate_accuracy: number | null
  candidate_macro_f1: number | null
  accuracy_delta: number | null
  decision: string | null
}

export interface FineTuneJobStatus extends FineTuneJob {
  epochs_completed: number
  total_epochs: number
  log_tail: string | null
}

export async function getBatch(batchId: string) {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/active-learning/batches/${batchId}`)
  return data
}

export async function exportBatch(batchId: string): Promise<Blob> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/active-learning/batches/${batchId}/export`, {
    responseType: 'blob',
  })
  return data
}

export async function uploadCandidateModel(formData: FormData) {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert/model-candidates/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getCandidateModels(): Promise<CandidateModel[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/model-candidates`)
  return data
}

export async function deleteCandidateModel(candidateId: string) {
  const { data } = await leafApi.delete(`${LEAF_API_BASE}/expert/model-candidates/${candidateId}`)
  return data
}

export async function deleteActiveLearningBatch(batchId: string) {
  const { data } = await leafApi.delete(`${LEAF_API_BASE}/expert/active-learning/batches/${batchId}`)
  return data
}

export async function checkFineTuneReadiness(): Promise<FineTuneReadiness> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/fine-tune/readiness`)
  return data
}

export async function startFineTuning() {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert/fine-tune/start`)
  return data
}

export async function getFineTuneJobs(): Promise<FineTuneJob[]> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/fine-tune/jobs`)
  return data
}

export async function getFineTuneJobStatus(jobId: string): Promise<FineTuneJobStatus> {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/fine-tune/status/${jobId}`)
  return data
}

export async function promoteCandidate(jobId: string) {
  const { data } = await leafApi.post(`${LEAF_API_BASE}/expert/fine-tune/${jobId}/promote`)
  return data
}

export async function getDeployedModel() {
  const { data } = await leafApi.get(`${LEAF_API_BASE}/expert/deployed-model`)
  return data
}

export default leafApi
