import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CheckCircle2, Play, Pause, MessageCircle } from 'lucide-react'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import ConfidenceBar from './ConfidenceBar'
import { diseaseColor, diseaseSinhalaName, formatConfidence } from '@/lib/disease'
import { useSpeechAudio } from '@/hooks/useSpeechAudio'
import type { VoiceDiagnosisResult } from '@/lib/voiceApi'

interface DiagnosisResultProps {
  result: VoiceDiagnosisResult
  onNewDiagnosis: () => void
}

export default function DiagnosisResult({ result, onNewDiagnosis }: DiagnosisResultProps) {
  const navigate = useNavigate()
  const color = diseaseColor(result.disease)
  const speech = useSpeechAudio(result.tts_audio_b64)

  // Novelty 4: Auto-play Sinhala TTS result (single shared clip — never overlaps)
  useEffect(() => {
    if (result.tts_audio_b64) {
      const timer = setTimeout(() => speech.play(), 600)
      return () => clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result.tts_audio_b64])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4"
    >
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5" style={{ color }} />
              <span className="font-sinhala text-xl font-bold text-forest">{diseaseSinhalaName(result.disease)}</span>
            </div>
            <p className="text-sm text-forest-muted">{result.disease}</p>
            {result.tts_audio_b64 && (
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={speech.status === 'playing' ? speech.pause : speech.play}
                  className="flex items-center gap-1.5 rounded-full bg-forest/10 px-3 py-1.5
                    text-xs font-semibold text-forest hover:bg-forest/20 transition-colors"
                  title={speech.status === 'playing' ? 'විරාමය | Pause' : 'ශ්‍රවණය | Play'}
                >
                  {speech.status === 'playing' ? (
                    <Pause className="h-3.5 w-3.5" />
                  ) : (
                    <Play className="h-3.5 w-3.5" />
                  )}
                  {speech.status === 'playing'
                    ? 'විරාමය | Pause'
                    : speech.status === 'paused'
                    ? 'දිගටම | Resume'
                    : 'ශ්‍රවණය | Play'}
                </button>
              </div>
            )}
          </div>
          <Badge tone={result.confidence >= 0.75 ? 'green' : 'amber'}>{formatConfidence(result.confidence)}</Badge>
        </div>

        {result.severity && !result.is_ood && (
          <div
            className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1
            text-xs font-semibold
            ${result.severity.level === 'severe'
              ? 'bg-red-100 text-red-700'
              : result.severity.level === 'moderate'
              ? 'bg-amber-light text-amber-dark'
              : 'bg-green-100 text-green-700'
            }`}
          >
            <span>{result.severity.label_si}</span>
            <span className="opacity-60">|</span>
            <span>{result.severity.label_en}</span>
          </div>
        )}

        {(result.sinhala_transcript || result.english_translation) && (
          <div className="mt-4 space-y-1 rounded-xl bg-beige p-4">
            {result.sinhala_transcript && <p className="font-sinhala text-sm text-forest">"{result.sinhala_transcript}"</p>}
            {result.english_translation && <p className="text-xs italic text-forest-muted">{result.english_translation}</p>}
          </div>
        )}
      </Card>

      <Card>
        <h4 className="mb-3 text-sm font-semibold text-forest-muted">Confidence Breakdown</h4>
        <ConfidenceBar allScores={result.all_scores} disease={result.disease} />

        {result.confidence_trajectory && result.confidence_trajectory.length > 1 && (
          <div className="mt-4 rounded-xl bg-beige p-4">
            <p className="mb-3 text-xs font-semibold uppercase text-forest-muted">
              විශ්වාසදායිතා පථය | Confidence Trajectory
            </p>
            <div className="flex items-end gap-2 h-16">
              {result.confidence_trajectory.map((step) => (
                <div key={step.step} className="flex flex-1 flex-col items-center justify-end gap-1">
                  <div
                    className="w-full rounded-t bg-amber transition-all duration-700"
                    style={{ height: `${Math.max(step.confidence * 40, 4)}px` }}
                    title={`${step.label}: ${Math.round(step.confidence * 100)}%`}
                  />
                  <span className="text-xs text-forest-muted">{step.step === 0 ? 'Start' : `Q${step.step}`}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <div className="flex gap-3">
        <Button variant="outline" className="flex-1" onClick={onNewDiagnosis}>
          නැවත | New Diagnosis
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          onClick={() =>
            navigate('/chat', {
              state: {
                initialMessage: `Tell me about treatment for ${result.disease}`,
              },
            })
          }
        >
          <MessageCircle className="h-4 w-4" />
          ප්‍රතිකාර | Treatment
        </Button>
      </div>
    </motion.div>
  )
}
