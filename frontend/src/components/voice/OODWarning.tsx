import { AlertCircle } from 'lucide-react'
import Card from '@/components/ui/Card'
import Button from '@/components/ui/Button'

interface OODWarningProps {
  reason?: string | null
  message?: string | null
  onRetry: () => void
}

export default function OODWarning({ reason, message, onRetry }: OODWarningProps) {
  return (
    <Card className="border-2 border-red-soft/30 text-center">
      <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-red-soft/10">
        <AlertCircle className="h-8 w-8 text-red-soft" />
      </div>
      <h3 className="font-sinhala text-lg font-bold text-forest">හඳුනාගත නොහැකි විය</h3>
      <p className="mt-1 text-sm text-forest-muted">
        {message || 'Could not confidently identify a rice disease from your description.'}
      </p>
      {reason && <p className="mt-2 text-xs text-forest-muted/70">({reason})</p>}
      <Button className="mt-5 w-full" onClick={onRetry}>
        නැවත උත්සාහ කරන්න | Try Again
      </Button>
    </Card>
  )
}
