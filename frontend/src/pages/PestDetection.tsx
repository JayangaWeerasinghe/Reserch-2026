import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import {
  BrainCircuit,
  CheckCircle2,
  History as HistoryIcon,
  ImagePlus,
  Loader2,
  ScanSearch,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react'
import toast from 'react-hot-toast'

import Card from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import PestResult from '@/components/pest/PestResult'
import PestHistory from '@/components/pest/PestHistory'

import { detectPest } from '@/lib/pestApi'
import type { PestDetectionResult } from '@/lib/pestApi'

import { useAuthStore } from '@/store/authStore'
import { useDiagnosisStore } from '@/store/diagnosisStore'

type Tab = 'detect' | 'history'

const ACCEPTED_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
]

const ANALYSIS_STEPS = [
  'Uploading image',
  'Validating image quality',
  'Running DenseNet121 classification',
  'Checking OOD and confidence',
  'Generating Grad-CAM',
  'Checking learned pest classes',
  'Preparing AI explanation',
  'Finalizing diagnosis',
]

function wait(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function getErrorMessage(
  error: unknown,
  fallback: string,
) {
  const response = error as {
    response?: {
      data?: {
        detail?: unknown
        message?: string
      }
    }
    message?: string
  }

  const detail = response?.response?.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }

        if (
          item &&
          typeof item === 'object' &&
          'msg' in item
        ) {
          return String(
            (item as { msg: unknown }).msg,
          )
        }

        return JSON.stringify(item)
      })
      .join('; ')
  }

  return (
    response?.response?.data?.message ||
    response?.message ||
    fallback
  )
}

/**
 * Create a small compressed preview for history.
 * The original uploaded image is NOT stored.
 */
async function createHistoryPreview(
  file: File,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    const objectUrl = URL.createObjectURL(file)

    image.onload = () => {
      URL.revokeObjectURL(objectUrl)

      const maxSize = 480

      let width = image.width
      let height = image.height

      if (width > height) {
        if (width > maxSize) {
          height = Math.round(
            (height * maxSize) / width,
          )
          width = maxSize
        }
      } else if (height > maxSize) {
        width = Math.round(
          (width * maxSize) / height,
        )
        height = maxSize
      }

      const canvas =
        document.createElement('canvas')

      canvas.width = width
      canvas.height = height

      const context =
        canvas.getContext('2d')

      if (!context) {
        reject(
          new Error(
            'Could not create image preview.',
          ),
        )
        return
      }

      context.drawImage(
        image,
        0,
        0,
        width,
        height,
      )

      resolve(
        canvas.toDataURL(
          'image/jpeg',
          0.65,
        ),
      )
    }

    image.onerror = () => {
      URL.revokeObjectURL(objectUrl)

      reject(
        new Error(
          'Could not create image preview.',
        ),
      )
    }

    image.src = objectUrl
  })
}

export default function PestDetection() {
  const [tab, setTab] =
    useState<Tab>('detect')

  const user =
    useAuthStore((state) => state.user)

  const pestHistory =
    useDiagnosisStore(
      (state) => state.pestHistory,
    )

  const deletePestEntry =
    useDiagnosisStore(
      (state) => state.deletePestEntry,
    )

  const clearPestHistory =
    useDiagnosisStore(
      (state) => state.clearPestHistory,
    )

  const myHistory =
    pestHistory.filter(
      (entry) =>
        entry.userId === user?.id,
    )

  return (
    <div className="mx-auto max-w-6xl space-y-6">

      {/* ================= TABS ================= */}

      <div className="flex gap-2 rounded-xl bg-beige p-1">

        {/* DETECT */}

        <button
          type="button"
          onClick={() => setTab('detect')}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-colors ${
            tab === 'detect'
              ? 'bg-white text-forest shadow-sm'
              : 'text-forest-muted hover:text-forest'
          }`}
        >
          <ScanSearch className="h-4 w-4" />
          Detect Pest
        </button>

        {/* HISTORY */}

        <button
          type="button"
          onClick={() => setTab('history')}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-colors ${
            tab === 'history'
              ? 'bg-white text-forest shadow-sm'
              : 'text-forest-muted hover:text-forest'
          }`}
        >
          <HistoryIcon className="h-4 w-4" />
          History
        </button>

      </div>

      {/* ================= DETECTION ================= */}

      {tab === 'detect' && (
        <DetectPanel />
      )}

      {/* ================= HISTORY ================= */}

      {tab === 'history' && (
        <PestHistory
          entries={myHistory}
          onDelete={deletePestEntry}
          onClear={() => {
            if (user) {
              clearPestHistory(user.id)
            }
          }}
        />
      )}

    </div>
  )
}


/* =========================================================
   DETECTION PANEL
========================================================= */

function DetectPanel() {
  const [file, setFile] =
    useState<File | null>(null)

  const [preview, setPreview] =
    useState<string | null>(null)

  const [result, setResult] =
    useState<PestDetectionResult | null>(null)

  const [detecting, setDetecting] =
    useState(false)

  const [analysisStep, setAnalysisStep] =
    useState(0)

  const [error, setError] =
    useState('')

  const inputRef =
    useRef<HTMLInputElement>(null)

  useEffect(() => {
    return () => {
      if (preview) {
        URL.revokeObjectURL(preview)
      }
    }
  }, [preview])

  function selectFile(
    selected: File | undefined,
  ) {
    if (!selected) return

    if (
      !ACCEPTED_TYPES.includes(
        selected.type,
      )
    ) {
      setError(
        'Please select a JPG, PNG or WEBP image.',
      )
      return
    }

    if (
      selected.size >
      10 * 1024 * 1024
    ) {
      setError(
        'Image is too large. Maximum size is 10 MB.',
      )
      return
    }

    if (preview) {
      URL.revokeObjectURL(preview)
    }

    setError('')
    setResult(null)
    setAnalysisStep(0)
    setFile(selected)

    setPreview(
      URL.createObjectURL(selected),
    )
  }

  function clearFile() {
    if (preview) {
      URL.revokeObjectURL(preview)
    }

    setFile(null)
    setPreview(null)
    setResult(null)
    setAnalysisStep(0)
    setError('')

    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  async function handleDetect() {
    if (!file) {
      toast.error(
        'Please select a pest image.',
      )
      return
    }

    setDetecting(true)
    setError('')
    setResult(null)
    setAnalysisStep(0)

    const startedAt = Date.now()

    /*
     * AI analysis animation runs alongside
     * the real backend request.
     *
     * Minimum visual analysis time:
     * approximately 4 seconds.
     */

    const stepTimer = window.setInterval(() => {
      setAnalysisStep((current) =>
        Math.min(
          current + 1,
          ANALYSIS_STEPS.length - 1,
        ),
      )
    }, 500)

    try {
      const data =
        await detectPest(file)

      /*
       * Keep the modern AI analysis screen
       * visible for at least 4 seconds.
       */

      const elapsed =
        Date.now() - startedAt

      const remaining =
        Math.max(
          0,
          4000 - elapsed,
        )

      if (remaining > 0) {
        await wait(remaining)
      }

      window.clearInterval(stepTimer)

      setAnalysisStep(
        ANALYSIS_STEPS.length - 1,
      )

      setResult(data)

      /*
       * Save detection to user's history.
       */

      const user =
        useAuthStore.getState().user

      if (user) {
        let imagePreview:
          | string
          | undefined

        /*
         * Create compressed thumbnail
         * only for history.
         *
         * Original image is not stored.
         */

        try {
          imagePreview =
            await createHistoryPreview(
              file,
            )
        } catch (previewError) {
          console.warn(
            'Could not create history image:',
            previewError,
          )
        }

        useDiagnosisStore
          .getState()
          .addPestEntry({
            pest_name:
              data.prediction,

            confidence:
              data.confidence,

            is_ood:
              data.status === 'unknown',

            userId:
              user.id,

            image_preview:
              imagePreview,

            source:
              data.source,
          })
      }

    } catch (err) {
      window.clearInterval(stepTimer)

      const message =
        getErrorMessage(
          err,
          'Detection failed. Please try again.',
        )

      setError(message)

      toast.error(message)

    } finally {
      window.clearInterval(stepTimer)
      setDetecting(false)
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">

      {/* ================= UPLOAD CARD ================= */}

      <Card>

        <div className="mb-4 flex items-start justify-between">

          <div>

            <h2 className="text-lg font-bold text-forest">
              1. Upload image
            </h2>

            <p className="mt-1 text-xs text-forest-muted">
              Upload a clear rice pest photo for all AI checks.
            </p>

          </div>

          <ImagePlus className="h-5 w-5 text-amber" />

        </div>

        {!preview ? (

          <button
            type="button"
            onClick={() =>
              inputRef.current?.click()
            }
            className="flex min-h-[310px] w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-beige bg-beige/30 transition hover:border-amber hover:bg-beige/50"
          >

            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-light text-amber-dark">
              <Upload className="h-8 w-8" />
            </span>

            <span className="text-base font-semibold text-forest">
              Choose pest image
            </span>

            <span className="text-xs text-forest-muted">
              JPG, PNG or WEBP · maximum 10 MB
            </span>

          </button>

        ) : (

          <div className="relative rounded-xl border border-beige bg-beige/20 p-3">

            <img
              src={preview}
              alt="Selected pest"
              className="mx-auto max-h-[420px] w-full rounded-lg object-contain"
            />

            <button
              type="button"
              onClick={clearFile}
              className="absolute right-5 top-5 rounded-full bg-white p-2 text-forest shadow"
              aria-label="Remove image"
            >
              <X className="h-4 w-4" />
            </button>

          </div>

        )}

        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(
            event: ChangeEvent<HTMLInputElement>,
          ) =>
            selectFile(
              event.target.files?.[0],
            )
          }
        />

        {file && (

          <div className="mt-3 flex items-center justify-between text-xs text-forest-muted">

            <span className="truncate pr-3">
              {file.name}
            </span>

            <button
              type="button"
              onClick={clearFile}
              className="shrink-0 text-red-soft hover:underline"
            >
              Remove
            </button>

          </div>

        )}

        <Button
          size="lg"
          className="mt-5 w-full"
          onClick={handleDetect}
          loading={detecting}
          disabled={!file || detecting}
        >
          {detecting
            ? 'Analyzing…'
            : 'හඳුනාගන්න | Detect Pest'}
        </Button>

        {error && (

          <div className="mt-3 rounded-xl border border-red-soft/20 bg-red-soft/5 px-4 py-3 text-xs text-red-soft">
            {error}
          </div>

        )}

        <div className="mt-5 grid grid-cols-3 gap-2 text-center">

          <FeatureMini
            icon={
              <ShieldCheck className="h-4 w-4" />
            }
            label="Quality Check"
          />

          <FeatureMini
            icon={
              <ScanSearch className="h-4 w-4" />
            }
            label="Grad-CAM"
          />

          <FeatureMini
            icon={
              <BrainCircuit className="h-4 w-4" />
            }
            label="OOD Detection"
          />

        </div>

      </Card>


      {/* ================= RESULT CARD ================= */}

      <Card>

        <div className="mb-4 flex items-start justify-between">

          <div>

            <h2 className="text-lg font-bold text-forest">
              2. AI analysis
            </h2>

            <p className="mt-1 text-xs text-forest-muted">
              Prediction, quality, OOD and explainable AI results.
            </p>

          </div>

          <ScanSearch className="h-5 w-5 text-green-soft" />

        </div>

        {detecting ? (

          <AnalysisProgress
            preview={preview}
            activeStep={analysisStep}
          />

        ) : !result ? (

          <div className="flex min-h-[430px] flex-col items-center justify-center text-center">

            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-green-soft/10 text-green-soft">
              <ScanSearch className="h-8 w-8" />
            </div>

            <h3 className="mt-4 font-semibold text-forest">
              Waiting for an image
            </h3>

            <p className="mt-1 max-w-xs text-xs leading-5 text-forest-muted">
              Upload and analyze a pest image to test all detection features.
            </p>

          </div>

        ) : (

          <PestResult result={result} />

        )}

      </Card>

    </div>
  )
}


/* =========================================================
   AI ANALYSIS PROGRESS
========================================================= */

function AnalysisProgress({
  preview,
  activeStep,
}: {
  preview: string | null
  activeStep: number
}) {
  const progress =
    Math.round(
      ((activeStep + 1) /
        ANALYSIS_STEPS.length) *
      100,
    )

  return (
    <div className="relative min-h-[430px] overflow-hidden rounded-2xl border border-green-soft/10 bg-gradient-to-b from-green-soft/[0.04] via-white to-beige/20 px-5 py-6">

      {/* Ambient glow */}

      <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-green-soft/10 blur-3xl" />

      <div className="pointer-events-none absolute -bottom-20 -left-16 h-40 w-40 rounded-full bg-amber/10 blur-3xl" />

      <div className="relative">

        {/* Header */}

        <div className="flex items-center justify-between">

          <div>

            <div className="flex items-center gap-2">

              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-green-soft/10 text-green-soft">

                <BrainCircuit className="h-5 w-5" />

              </span>

              <div>

                <h3 className="text-base font-bold text-forest">
                  Analyzing Pest Image
                </h3>

                <p className="text-[10px] text-forest-muted">
                  PaddyGuard AI Vision Engine
                </p>

              </div>

            </div>

          </div>

          <span className="rounded-full bg-green-soft/10 px-2.5 py-1 text-[10px] font-bold text-green-soft">
            {progress}%
          </span>

        </div>


        {/* Image scan preview */}

        <div className="relative mx-auto mt-5 h-28 w-40 overflow-hidden rounded-2xl border border-green-soft/10 bg-beige/40 shadow-sm">

          {preview ? (

            <img
              src={preview}
              alt="Analyzing pest"
              className="h-full w-full object-cover opacity-80"
            />

          ) : (

            <div className="flex h-full items-center justify-center text-green-soft">
              <ScanSearch className="h-8 w-8" />
            </div>

          )}

          <div className="absolute inset-0 bg-gradient-to-t from-forest/20 via-transparent to-transparent" />

          {/* Scanning beam */}

          <div className="absolute left-0 right-0 top-0 h-0.5 bg-green-soft shadow-[0_0_12px_rgba(34,197,94,0.8)] animate-[bounce_1.8s_ease-in-out_infinite]" />

          <div className="absolute bottom-2 left-2 rounded-md bg-white/90 px-2 py-1 text-[9px] font-semibold text-forest shadow-sm">
            AI VISION SCAN
          </div>

        </div>


        {/* Progress bar */}

        <div className="mt-5">

          <div className="mb-2 flex items-center justify-between text-[10px]">

            <span className="font-semibold text-forest-muted">
              AI pipeline progress
            </span>

            <span className="font-bold text-green-soft">
              {activeStep + 1}/{ANALYSIS_STEPS.length}
            </span>

          </div>

          <div className="h-1.5 overflow-hidden rounded-full bg-beige">

            <div
              className="h-full rounded-full bg-green-soft transition-all duration-500 ease-out"
              style={{
                width: `${progress}%`,
              }}
            />

          </div>

        </div>


        {/* Pipeline steps */}

        <div className="mt-5 space-y-2">

          {ANALYSIS_STEPS.map(
            (step, index) => {

              const completed =
                index < activeStep

              const active =
                index === activeStep

              return (

                <div
                  key={step}
                  className={`flex items-center gap-3 rounded-xl px-3 py-2 transition-all duration-500 ${
                    active
                      ? 'bg-green-soft/10 text-forest shadow-sm'
                      : completed
                        ? 'bg-white/70 text-forest'
                        : 'text-forest-muted/50'
                  }`}
                >

                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-all duration-500 ${
                      completed
                        ? 'bg-green-soft text-white'
                        : active
                          ? 'border-2 border-green-soft bg-white text-green-soft'
                          : 'border border-forest-muted/20 bg-white/50'
                    }`}
                  >

                    {completed ? (

                      <CheckCircle2 className="h-4 w-4" />

                    ) : active ? (

                      <Loader2 className="h-3.5 w-3.5 animate-spin" />

                    ) : (

                      <span className="h-1.5 w-1.5 rounded-full bg-forest-muted/30" />

                    )}

                  </span>

                  <span
                    className={`text-xs ${
                      active || completed
                        ? 'font-semibold'
                        : 'font-medium'
                    }`}
                  >
                    {step}
                  </span>

                  {active && (

                    <span className="ml-auto text-[9px] font-bold uppercase tracking-wide text-green-soft">
                      processing
                    </span>

                  )}

                </div>

              )
            },
          )}

        </div>


        {/* Footer */}

        <div className="mt-4 flex items-center justify-center gap-2 text-[10px] text-forest-muted">

          <ShieldCheck className="h-3.5 w-3.5 text-green-soft" />

          Quality • OOD • Grad-CAM

        </div>

      </div>

    </div>
  )
}


/* =========================================================
   FEATURE MINI
========================================================= */

function FeatureMini({
  icon,
  label,
}: {
  icon: ReactNode
  label: string
}) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-xl bg-beige/50 px-2 py-2 text-[10px] font-semibold text-forest-muted">
      {icon}
      {label}
    </div>
  )
}