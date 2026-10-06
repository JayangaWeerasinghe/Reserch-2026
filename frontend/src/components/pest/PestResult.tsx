import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Bug, CheckCircle2, Info, MessageCircle, ScanSearch, ShieldAlert } from 'lucide-react'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { formatConfidence } from '@/lib/disease'
import type { PestDetectionResult } from '@/lib/pestApi'

function sourceLabel(source: PestDetectionResult['source']) {
  switch (source) {
    case 'fine_tuned':
      return 'Selective Fine-Tuned DenseNet121'
    case 'few_shot':
      return 'Prototype Few-Shot Baseline'
    case 'ood':
      return 'Mahalanobis OOD'
    case 'quality_check':
      return 'Image Quality Check'
    default:
      return 'DenseNet121 Base Model'
  }
}

export default function PestResult({ result }: { result: PestDetectionResult }) {
  const navigate = useNavigate()
  const quality = result.quality

  if (result.source === 'quality_check' || result.prediction === 'Image Quality Too Low') {
    return (
      <div className="space-y-4">
        <Card className="border-2 border-amber/30">
          <div className="flex items-start gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-amber-light text-amber-dark">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <h3 className="font-sinhala text-lg font-bold text-forest">Image Quality Too Low</h3>
              <p className="mt-1 text-sm text-forest-muted">{result.message}</p>
            </div>
          </div>
        </Card>
        <QualityCard quality={quality} />
      </div>
    )
  }

  if (result.status === 'unknown') {
    return (
      <div className="space-y-4">
        <Card className="border-2 border-red-soft/20">
          <div className="flex items-start gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-red-soft/10 text-red-soft">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div className="min-w-0">
              <div className="mb-1 flex items-center gap-2">
                <Badge tone="amber">Unknown / Rejected</Badge>
              </div>
              <h3 className="font-sinhala text-lg font-bold text-forest">Unknown Pest</h3>
              <p className="mt-1 text-sm leading-5 text-forest-muted">{result.message}</p>
              {result.ood_score !== null && (
                <p className="mt-2 text-xs text-forest-muted">
                  OOD method: {result.ood_method} · Score: {result.ood_score}
                </p>
              )}
            </div>
          </div>
        </Card>
        <QualityCard quality={quality} />
        <InfoCard text="If this is a real new pest, use Teach New Pest and provide 5–20 labelled images." />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2">
              <Bug className="h-5 w-5 shrink-0 text-amber" />
              <Badge tone={result.status === 'known' ? 'green' : 'amber'}>
                {result.status === 'known' ? 'Known pest' : 'Needs verification'}
              </Badge>
            </div>
            <h3 className="break-words text-2xl font-bold capitalize text-forest">
              {result.prediction.replace(/_/g, ' ')}
            </h3>
          </div>

          <div className="shrink-0 text-right">
            <strong className="block text-2xl text-green-soft">
              {formatConfidence(result.confidence)}
            </strong>
            <span className="text-[11px] text-forest-muted">
              {result.source === 'few_shot' ? 'similarity' : 'confidence'}
            </span>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-lg bg-beige px-2.5 py-1.5 text-[11px] text-forest-muted">
            Source: {sourceLabel(result.source)}
          </span>
          <span className="rounded-lg bg-beige px-2.5 py-1.5 text-[11px] text-forest-muted">
            OOD: {result.ood_method}
          </span>
        </div>

        <div className="mt-3 flex items-start gap-2 rounded-xl bg-beige/50 px-3 py-2.5 text-xs leading-5 text-forest-muted">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-soft" />
          <span>{result.message}</span>
        </div>

        {result.few_shot_similarity !== null && (
          <div className="mt-3 text-xs text-forest-muted">
            Learned-class score: <strong className="text-forest">{formatConfidence(result.few_shot_similarity)}</strong>
          </div>
        )}
      </Card>

      <QualityCard quality={quality} />

      {result.gradcam_image_base64 ? (
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <ScanIcon />
            <h4 className="text-sm font-bold text-forest">Explainable AI · Grad-CAM</h4>
          </div>

          <div className="rounded-xl bg-beige/30 p-2">
            <img
              src={`data:image/jpeg;base64,${result.gradcam_image_base64}`}
              alt="Grad-CAM explanation heatmap"
              className="w-full rounded-lg object-cover"
            />
          </div>

          <p className="mt-2 text-xs leading-5 text-forest-muted">
            Highlighted regions show the areas that contributed most to the model prediction.
          </p>
        </Card>
      ) : (
        <InfoCard text="Grad-CAM is unavailable for this result because the image was rejected or treated as a hard unknown." />
      )}

      <Button
        variant="outline"
        className="w-full"
        onClick={() =>
          navigate('/chat', {
            state: {
              initialMessage: `Tell me about treatment for ${result.prediction}`,
            },
          })
        }
      >
        <MessageCircle className="h-4 w-4" />
        ප්‍රතිකාර | Treatment
      </Button>
    </div>
  )
}

function QualityCard({
  quality,
}: {
  quality: PestDetectionResult['quality']
}) {
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-bold text-forest">Image Quality</h4>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
          quality.passed
            ? 'bg-green-soft/10 text-green-soft'
            : 'bg-red-soft/10 text-red-soft'
        }`}>
          {quality.passed ? 'Acceptable' : 'Needs better image'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Metric label="Blur score" value={quality.blur_score} />
        <Metric label="Brightness" value={quality.brightness} />
        <Metric label="Contrast" value={quality.contrast} />
        <Metric label="Edge density" value={quality.edge_density} />
        <Metric label="Resolution" value={quality.resolution} />
      </div>

      {quality.warnings.length > 0 && (
        <div className="mt-3 rounded-xl border border-amber/20 bg-amber-light/40 p-3 text-xs leading-5 text-amber-dark">
          {quality.warnings.map((warning) => (
            <div key={warning}>⚠️ {warning}</div>
          ))}
        </div>
      )}
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl bg-beige/40 p-2.5">
      <span className="block text-[10px] text-forest-muted">{label}</span>
      <strong className="mt-1 block break-words text-xs text-forest">
        {typeof value === 'number' ? value.toFixed(2) : value}
      </strong>
    </div>
  )
}

function InfoCard({ text }: { text: string }) {
  return (
    <Card className="bg-beige/30">
      <div className="flex items-start gap-2 text-xs leading-5 text-forest-muted">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber" />
        <span>{text}</span>
      </div>
    </Card>
  )
}

function ScanIcon() {
  return <ScanSearch className="h-4 w-4 text-green-soft" />
}