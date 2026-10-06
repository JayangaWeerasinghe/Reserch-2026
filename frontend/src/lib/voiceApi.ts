import api from './api'

export interface VoiceDiagnosisResult {
  disease: string
  label_id: number
  confidence: number
  is_ood: boolean
  ood_reason: string | null
  needs_followup: boolean
  status: string
  message: string | null
  all_scores: Record<string, number>
  sinhala_transcript?: string
  english_translation?: string
  session_id: string | null
  followup_question: string | null
  followup_question_en: string | null
  question_number?: number
  max_questions?: number
  followup_complete?: boolean
  tts_audio_b64?:         string | null
  question_tts_b64?:      string | null
  severity?: {
    level:    'mild' | 'moderate' | 'severe'
    score:    1 | 2 | 3
    label_si: string
    label_en: string
  } | null
  confidence_trajectory?: Array<{
    step:       number
    label:      string
    disease:    string
    confidence: number
  }>
  audio_quality?: {
    passed:        boolean
    snr_db:        number | null
    silence_ratio: number | null
    duration_sec:  number | null
  } | null
}

export async function diagnoseVoice(audio: Blob, filename: string): Promise<VoiceDiagnosisResult> {
  const form = new FormData()
  form.append('audio', audio, filename)
  const { data } = await api.post('/api/v1/voice/diagnose', form)
  return data
}

export async function submitFollowUp(answer: string, sessionId: string): Promise<VoiceDiagnosisResult> {
  const { data } = await api.post('/api/v1/voice/followup', { answer, session_id: sessionId })
  return data
}
