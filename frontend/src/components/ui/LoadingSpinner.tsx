import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps {
  size?: number
  label?: string
  labelEn?: string
}

export default function LoadingSpinner({ size = 40, label, labelEn }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-forest">
      <Loader2 style={{ width: size, height: size }} className="animate-spin" />
      {label && <p className="font-sinhala text-lg font-medium">{label}</p>}
      {labelEn && <p className="text-sm text-forest-muted">{labelEn}</p>}
    </div>
  )
}
