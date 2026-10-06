import { motion } from 'framer-motion'
import { diseaseColor, diseaseSinhalaName, formatConfidence } from '@/lib/disease'

interface ConfidenceBarProps {
  allScores: Record<string, number>
  disease: string
}

export default function ConfidenceBar({ allScores, disease }: ConfidenceBarProps) {
  const entries = Object.entries(allScores).sort((a, b) => b[1] - a[1])

  return (
    <div className="space-y-3">
      {entries.map(([name, score]) => {
        const isWinner = name === disease
        return (
          <div key={name}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className={`font-sinhala ${isWinner ? 'font-bold text-forest' : 'text-forest-light'}`}>
                {diseaseSinhalaName(name)} · {name}
              </span>
              <span className={isWinner ? 'font-bold text-forest' : 'text-forest-muted'}>{formatConfidence(score)}</span>
            </div>
            <div className={`w-full overflow-hidden rounded-full bg-beige ${isWinner ? 'h-3' : 'h-2'}`}>
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: diseaseColor(name) }}
                initial={{ width: 0 }}
                animate={{ width: `${score * 100}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
