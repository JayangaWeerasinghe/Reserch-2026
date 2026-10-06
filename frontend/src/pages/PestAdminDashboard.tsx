import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import {
  BrainCircuit,
  CheckCircle2,
  LogOut,
  ShieldCheck,
  Trash2,
  Upload,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

import Card from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import EmptyState from '@/components/ui/EmptyState'

import {
  deleteLearnedPest,
  getLearnedPestClasses,
  teachNewPest,
} from '@/lib/pestApi'

import { usePestAuthStore } from '@/store/pestAuthStore'

type LearnMethod = 'fine_tune' | 'prototype'

const ACCEPTED_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
]

function getErrorMessage(error: unknown, fallback: string) {
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

export default function PestAdminDashboard() {
  const navigate = useNavigate()

  const pestAdmin = usePestAuthStore((state) => state.user)
  const logout = usePestAuthStore((state) => state.logout)

  const [className, setClassName] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [classesLoading, setClassesLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [classes, setClasses] = useState<string[]>([])
  const [method, setMethod] = useState<LearnMethod>('fine_tune')

  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    void loadClasses()
  }, [])

  async function loadClasses() {
    setClassesLoading(true)

    try {
      const loaded = await getLearnedPestClasses()
      setClasses(loaded)
    } catch (err) {
      console.error('Could not load learned pest classes:', err)
    } finally {
      setClassesLoading(false)
    }
  }

  function handleLogout() {
    logout()
    navigate('/pest-admin-login')
  }

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? [])

    const invalid = selected.filter(
      (file) => !ACCEPTED_TYPES.includes(file.type),
    )

    if (invalid.length > 0) {
      setError('Only JPG, PNG and WEBP images are allowed.')
      setFiles([])
      return
    }

    if (selected.length < 5) {
      setError('Select between 5 and 20 labelled images.')
    } else if (selected.length > 20) {
      setError('Maximum 20 labelled images are allowed.')
    } else {
      setError('')
    }

    setFiles(selected.slice(0, 20))
  }

  async function handleTeach() {
    setError('')
    setMessage('')

    const name = className.trim()

    if (!name) {
      setError('Enter a name for the new pest.')
      return
    }

    if (files.length < 5 || files.length > 20) {
      setError('Select between 5 and 20 labelled images.')
      return
    }

    setLoading(true)

    try {
      const data = await teachNewPest(
        name,
        files,
        method,
      )

      setMessage(
        data.message ||
          'New pest learned successfully.',
      )

      toast.success(
        data.message ||
          'New pest learned successfully.',
      )

      setClassName('')
      setFiles([])

      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      await loadClasses()
    } catch (err) {
      const messageText = getErrorMessage(
        err,
        'Few-shot learning failed.',
      )

      setError(messageText)
      toast.error(messageText)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(name: string) {
    const confirmed = window.confirm(
      `Delete learned pest class "${name}"?`,
    )

    if (!confirmed) {
      return
    }

    try {
      await deleteLearnedPest(name)

      await loadClasses()

      toast.success(`Deleted ${name}.`)
    } catch (err) {
      const messageText = getErrorMessage(
        err,
        'Could not delete learned pest class.',
      )

      setError(messageText)
      toast.error(messageText)
    }
  }

  if (!pestAdmin) {
    return null
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">

      {/* Header */}
      <div className="flex flex-col gap-4 rounded-2xl bg-forest p-5 text-white shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-forest-light">
            <BrainCircuit className="h-6 w-6 text-amber" />
          </div>

          <div>
            <h1 className="text-lg font-bold">
              Pest Model Administration
            </h1>

            <p className="mt-1 text-xs text-white/70">
              Logged in as {pestAdmin.username} · PEST ADMIN
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="flex items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-white/80 transition hover:bg-white/10 hover:text-white"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>

      {/* Security notice */}
      <Card className="border border-green-soft/20 bg-green-soft/5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-soft/10">
            <ShieldCheck className="h-5 w-5 text-green-soft" />
          </div>

          <div>
            <h2 className="text-sm font-bold text-forest">
              Authorized Pest Model Management
            </h2>

            <p className="mt-1 text-xs leading-5 text-forest-muted">
              This section is restricted to the Pest Administrator.
              You can add new pest classes using selective
              fine-tuning or create a prototype baseline.
            </p>
          </div>
        </div>
      </Card>

      {/* Research explanation */}
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-forest">
              Few-Shot New Pest Learning
            </h2>

            <p className="mt-1 max-w-3xl text-xs leading-5 text-forest-muted">
              Adapt DenseNet121 to a new rice pest using only
              5–20 labelled images. The original model is never
              overwritten.
            </p>
          </div>

          <BrainCircuit className="h-6 w-6 shrink-0 text-green-soft" />
        </div>

        <div className="mt-5 rounded-xl border border-green-soft/20 bg-green-soft/5 p-4 text-xs leading-5 text-forest">
          <span className="font-bold">
            Research pipeline:
          </span>{' '}
          Unknown Pest → collect 5–20 labelled examples →
          selectively fine-tune the final DenseNet121 layers →
          test recognition of the new pest without retraining
          the whole model from scratch.
        </div>

        {/* Inputs */}
        <div className="mt-6 grid gap-4 md:grid-cols-2">

          <label className="block">
            <span className="mb-2 block text-xs font-bold text-forest-muted">
              New pest name
            </span>

            <input
              value={className}
              onChange={(event) =>
                setClassName(event.target.value)
              }
              placeholder="e.g. Rice Armyworm"
              className="w-full rounded-xl border border-beige bg-white px-3 py-3 text-sm text-forest outline-none transition focus:border-green-soft"
            />
          </label>

          <div>
            <span className="mb-2 block text-xs font-bold text-forest-muted">
              Labelled images (5–20)
            </span>

            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-forest-muted/40 bg-beige/20 px-3 py-3 text-xs text-forest transition hover:border-green-soft">
              <Upload className="h-4 w-4 text-amber" />

              <span>
                {files.length
                  ? `${files.length} files selected`
                  : 'Choose labelled images'}
              </span>

              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handleFiles}
              />
            </label>
          </div>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="mt-4 grid gap-1 rounded-xl bg-beige/30 p-3 text-xs text-forest-muted sm:grid-cols-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="truncate"
              >
                {index + 1}. {file.name}
              </div>
            ))}
          </div>
        )}

        {/* Methods */}
        <div className="mt-6 grid gap-3 md:grid-cols-2">

          <button
            type="button"
            onClick={() => setMethod('fine_tune')}
            className={`rounded-xl border p-4 text-left transition ${
              method === 'fine_tune'
                ? 'border-green-soft bg-green-soft/5'
                : 'border-beige bg-white hover:bg-beige/20'
            }`}
          >
            <div className="flex items-center gap-2 text-sm font-bold text-forest">
              <BrainCircuit className="h-4 w-4 text-green-soft" />
              Selective Fine-Tuning
            </div>

            <p className="mt-1 text-xs leading-5 text-forest-muted">
              Recommended research method. Fine-tunes selected
              DenseNet121 layers instead of the entire network.
            </p>

            {method === 'fine_tune' && (
              <div className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-green-soft">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Selected
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() => setMethod('prototype')}
            className={`rounded-xl border p-4 text-left transition ${
              method === 'prototype'
                ? 'border-green-soft bg-green-soft/5'
                : 'border-beige bg-white hover:bg-beige/20'
            }`}
          >
            <div className="text-sm font-bold text-forest">
              Prototype Baseline
            </div>

            <p className="mt-1 text-xs leading-5 text-forest-muted">
              Frozen DenseNet121 embeddings used as a research
              comparison baseline.
            </p>

            {method === 'prototype' && (
              <div className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-green-soft">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Selected
              </div>
            )}
          </button>
        </div>

        {/* Action */}
        <Button
          size="lg"
          className="mt-5"
          onClick={handleTeach}
          loading={loading}
          disabled={
            loading ||
            !className.trim() ||
            files.length < 5 ||
            files.length > 20
          }
        >
          {loading
            ? method === 'fine_tune'
              ? 'Fine-tuning…'
              : 'Learning…'
            : method === 'fine_tune'
              ? 'Adapt New Pest'
              : 'Create Prototype'}
        </Button>

        {message && (
          <div className="mt-4 rounded-xl border border-green-soft/20 bg-green-soft/5 px-4 py-3 text-xs text-green-soft">
            ✓ {message}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-xl border border-red-soft/20 bg-red-soft/5 px-4 py-3 text-xs text-red-soft">
            {error}
          </div>
        )}
      </Card>

      {/* Learned classes */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-forest">
              Learned Pest Classes
            </h2>

            <p className="mt-1 text-xs text-forest-muted">
              Pest classes currently available to the model.
            </p>
          </div>

          <span className="rounded-full bg-beige px-3 py-1 text-xs font-semibold text-forest-muted">
            {classes.length} learned
          </span>
        </div>

        {classesLoading ? (
          <div className="py-8 text-center text-sm text-forest-muted">
            Loading learned classes…
          </div>
        ) : classes.length === 0 ? (
          <EmptyState
            title="No pest classes learned yet"
            description="Use the form above to adapt the model to a new pest."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {classes.map((name) => (
              <div
                key={name}
                className="flex items-center justify-between rounded-xl border border-beige bg-beige/30 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold capitalize text-forest">
                    {name.replace(/_/g, ' ')}
                  </p>

                  <p className="mt-1 text-[10px] text-green-soft">
                    Learned class
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => void handleDelete(name)}
                  className="ml-3 rounded-lg p-2 text-red-soft transition hover:bg-red-soft/10"
                  title={`Delete ${name}`}
                  aria-label={`Delete ${name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* How it works */}
      <Card>
        <h2 className="text-sm font-bold text-forest">
          How Pest Model Adaptation Works
        </h2>

        <ol className="mt-3 list-decimal space-y-2 pl-5 text-xs leading-5 text-forest-muted">
          <li>
            Collect 5–20 images belonging to the same new pest.
          </li>
          <li>
            Enter the new pest class name.
          </li>
          <li>
            Selective Fine-Tuning keeps the original DenseNet121
            knowledge in the frozen layers.
          </li>
          <li>
            Selected deeper layers and the classifier are fine-tuned.
          </li>
          <li>
            The original base checkpoint is never overwritten.
          </li>
          <li>
            The adapted model is saved separately.
          </li>
          <li>
            The new pest can then be tested from the normal Pest
            Detection page.
          </li>
        </ol>
      </Card>
    </div>
  )
}