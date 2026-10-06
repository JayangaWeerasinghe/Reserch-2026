import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import Button from '@/components/ui/Button'
import { formatConfidence } from '@/lib/disease'

interface FollowUpDialogProps {
  question: string
  questionEn: string
  questionNumber: number
  maxQuestions: number
  confidence: number
  onAnswer: (answer: string) => void
  onSkip: () => void
  loading?: boolean
}

export default function FollowUpDialog({
  question,
  questionEn,
  questionNumber,
  maxQuestions,
  confidence,
  onAnswer,
  onSkip,
  loading = false,
}: FollowUpDialogProps) {
  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-end justify-center">
        <motion.div
          className="absolute inset-0 bg-black/30"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          onClick={onSkip}
        />
        <motion.div
          className="relative w-full max-w-lg rounded-t-3xl bg-white p-6 shadow-2xl"
          initial={{ y: 300 }}
          animate={{ y: 0 }}
          transition={{ type: 'spring', damping: 28, stiffness: 300 }}
        >
          <div className="mx-auto mb-4 h-1.5 w-12 rounded-full bg-beige" />

          <div className="mb-3 flex items-center justify-center gap-1.5">
            {Array.from({ length: maxQuestions }).map((_, i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all ${
                  i < questionNumber ? 'w-6 bg-amber' : 'w-1.5 bg-beige'
                }`}
              />
            ))}
          </div>

          <div className="mb-4 flex items-center gap-2 rounded-xl bg-amber-light px-4 py-2.5 text-sm text-amber-dark">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>අඩු විශ්වාසනීයත්වයක් ({formatConfidence(confidence)}) — තවත් විස්තර අවශ්‍යයි</span>
          </div>

          <div className="mb-6 rounded-2xl bg-beige p-5 text-center">
            <p className="font-sinhala text-lg font-semibold text-forest">{question}</p>
            <p className="mt-1 text-sm italic text-forest-muted">{questionEn}</p>
          </div>

          <p className="mb-2 text-center text-xs text-forest-muted">
            ඔබේ පිළිතුර තෝරන්න | Choose your answer
          </p>
          <div className="flex gap-3" role="group" aria-label="Follow-up answer">
            <div className="flex-1 flex flex-col items-center gap-1">
              <span className="text-xs text-forest-muted">රෝගය නොමැත | Symptom absent</span>
              <Button
                className="w-full"
                variant="outline"
                onClick={() => onAnswer('නෑ')}
                loading={loading}
                aria-label="No — this symptom is not present"
                title="No — this symptom is not present"
              >
                නෑ | No
              </Button>
            </div>
            <div className="flex-1 flex flex-col items-center gap-1">
              <span className="text-xs text-forest-muted">රෝගය ඇත | Symptom present</span>
              <Button
                className="w-full"
                variant="primary"
                onClick={() => onAnswer('ඔව්')}
                loading={loading}
                aria-label="Yes — this symptom is present"
                title="Yes — this symptom is present"
              >
                ඔව් | Yes
              </Button>
            </div>
          </div>

          <button onClick={onSkip} className="mt-4 w-full text-center text-sm text-forest-muted underline">
            මඟ හරින්න | Skip
          </button>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
