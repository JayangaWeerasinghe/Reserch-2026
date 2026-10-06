import { AlertCircle, CloudSun, Leaf } from 'lucide-react'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import { diseaseColor, diseaseSinhalaName, formatConfidence, severityLabel } from '@/lib/disease'
import type { AnalyzeResult } from '@/lib/leafApi'

export default function ResultCard({ result }: { result: AnalyzeResult }) {
  const { prediction } = result

  if (prediction.status === 'OOD') {
    return (
      <Card className="border-2 border-red-soft/30 text-center">
        <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-red-soft/10">
          <AlertCircle className="h-8 w-8 text-red-soft" />
        </div>
        <h3 className="font-sinhala text-lg font-bold text-forest">ගොයම් කොළයක් නොවේ</h3>
        <p className="mt-1 text-sm text-forest-muted">This image doesn't look like a rice leaf. Try a clearer close-up photo.</p>
      </Card>
    )
  }

  const color = diseaseColor(prediction.prediction)
  const severity = severityLabel(prediction.severity_percentage)
  const weather = result.weather as Record<string, unknown>
  const yieldLoss = result.yield_loss as Record<string, unknown> | null

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <Leaf className="h-5 w-5" style={{ color }} />
              <span className="font-sinhala text-xl font-bold text-forest">{diseaseSinhalaName(prediction.prediction)}</span>
            </div>
            <p className="text-sm text-forest-muted">{prediction.prediction.replace(/_/g, ' ')}</p>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <Badge tone={prediction.confidence >= 0.75 ? 'green' : 'amber'}>{formatConfidence(prediction.confidence)}</Badge>
            {prediction.severity_percentage != null && (
              <Badge tone={severity.label === 'Severe' ? 'red' : severity.label === 'Moderate' ? 'amber' : 'green'}>
                {severity.label} · {prediction.severity_percentage.toFixed(1)}%
              </Badge>
            )}
          </div>
        </div>

        {prediction.needs_expert_review && (
          <div className="mt-3 rounded-xl bg-amber-light px-4 py-2 text-xs text-amber-dark">
            Low confidence — this case has been queued for expert review.
          </div>
        )}
      </Card>

      {prediction.gradcam_base64 && (
        <Card>
          <h4 className="mb-2 text-sm font-semibold text-forest-muted">Grad-CAM — Affected Region</h4>
          <img
            src={`data:image/png;base64,${prediction.gradcam_base64}`}
            alt="Grad-CAM heatmap"
            className="w-full rounded-xl object-cover"
          />
        </Card>
      )}

      {yieldLoss && Object.keys(yieldLoss).length > 0 && (
        <Card>
          <h4 className="mb-2 text-sm font-semibold text-forest-muted">Estimated Yield Impact</h4>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {'predicted_loss_percentage' in yieldLoss && (
              <div>
                <p className="text-forest-muted">Predicted Loss</p>
                <p className="font-bold text-forest">{String(yieldLoss.predicted_loss_percentage)}%</p>
              </div>
            )}
            {'estimated_loss_kg' in yieldLoss && (
              <div>
                <p className="text-forest-muted">Estimated Loss</p>
                <p className="font-bold text-forest">{String(yieldLoss.estimated_loss_kg)} kg</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {weather && Object.keys(weather).length > 0 && (
        <Card>
          <div className="mb-2 flex items-center gap-2">
            <CloudSun className="h-4 w-4 text-forest-muted" />
            <h4 className="text-sm font-semibold text-forest-muted">Weather Context — {result.location?.city}</h4>
          </div>
          <div className="flex flex-wrap gap-4 text-sm text-forest">
            {Object.entries(weather).slice(0, 6).map(([k, v]) => (
              <div key={k}>
                <span className="text-forest-muted">{k}: </span>
                <span className="font-medium">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h4 className="mb-3 text-sm font-semibold text-forest-muted">Top Predictions</h4>
        <div className="space-y-2">
          {Object.entries(prediction.class_probabilities)
            .sort((a, b) => b[1] - a[1])
            .map(([name, score]) => (
              <div key={name} className="flex items-center justify-between text-sm">
                <span className="text-forest">{name.replace(/_/g, ' ')}</span>
                <span className="font-medium text-forest-muted">{formatConfidence(score)}</span>
              </div>
            ))}
        </div>
      </Card>

      <Card className="bg-beige">
        <p className="text-xs text-forest">{result.advisory.message}</p>
        <p className="mt-1 text-xs font-semibold text-red-soft">{result.advisory.safety}</p>
      </Card>
    </div>
  )
}
