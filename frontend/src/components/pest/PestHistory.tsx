import { useMemo, useState } from 'react'
import {
  Activity,
  BarChart3,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Database,
  Image as ImageIcon,
  Search,
  ShieldAlert,
  Trash2,
  X,
} from 'lucide-react'

import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmDialog from '@/components/ui/ConfirmDialog'

import {
  formatConfidence,
  formatDate,
} from '@/lib/disease'

import type { PestHistoryEntry } from '@/store/diagnosisStore'

interface PestHistoryProps {
  entries: PestHistoryEntry[]
  onDelete: (id: string) => void
  onClear: () => void
}

type FilterType = 'all' | 'known' | 'unknown' | 'fine_tuned'

function sourceLabel(source?: string) {
  switch (source) {
    case 'fine_tuned':
      return 'Selective Fine-Tuning'

    case 'few_shot':
      return 'Few-Shot Learning'

    case 'ood':
      return 'Mahalanobis OOD'

    case 'base_model':
      return 'DenseNet121'

    case 'quality_check':
      return 'Quality Check'

    default:
      return 'AI Detection'
  }
}

function sourceShortLabel(source?: string) {
  switch (source) {
    case 'fine_tuned':
      return 'Fine-Tuned'

    case 'few_shot':
      return 'Few-Shot'

    case 'ood':
      return 'OOD'

    case 'base_model':
      return 'DenseNet121'

    default:
      return 'AI'
  }
}

export default function PestHistory({
  entries,
  onDelete,
  onClear,
}: PestHistoryProps) {
  const [filter, setFilter] = useState<FilterType>('all')
  const [search, setSearch] = useState('')
  const [selectedEntry, setSelectedEntry] =
    useState<PestHistoryEntry | null>(null)

  const [pendingDelete, setPendingDelete] =
    useState<string | null>(null)

  const [clearDialog, setClearDialog] =
    useState(false)

  const [deleting, setDeleting] =
    useState(false)

  const stats = useMemo(() => {
    const total = entries.length

    const unknown = entries.filter(
      (entry) => entry.is_ood,
    ).length

    const known = total - unknown

    const fineTuned = entries.filter(
      (entry) => entry.source === 'fine_tuned',
    ).length

    const average =
      total > 0
        ? entries.reduce(
            (sum, entry) => sum + entry.confidence,
            0,
          ) / total
        : 0

    return {
      total,
      known,
      unknown,
      fineTuned,
      average,
    }
  }, [entries])

  const filteredEntries = useMemo(() => {
    const query = search.trim().toLowerCase()

    return entries.filter((entry) => {
      const name = entry.pest_name.toLowerCase()

      const matchesSearch =
        !query ||
        name.includes(query) ||
        sourceLabel(entry.source)
          .toLowerCase()
          .includes(query)

      let matchesFilter = true

      if (filter === 'known') {
        matchesFilter = !entry.is_ood
      }

      if (filter === 'unknown') {
        matchesFilter = entry.is_ood
      }

      if (filter === 'fine_tuned') {
        matchesFilter =
          entry.source === 'fine_tuned'
      }

      return matchesSearch && matchesFilter
    })
  }, [entries, filter, search])

  function handleConfirmDelete() {
    if (!pendingDelete) return

    setDeleting(true)

    try {
      onDelete(pendingDelete)
    } finally {
      setDeleting(false)
      setPendingDelete(null)
    }
  }

  function handleClear() {
    setClearDialog(false)
    onClear()
  }

  if (entries.length === 0) {
    return (
      <Card className="mx-auto max-w-6xl">
        <EmptyState
          title="No pest detections yet"
          description="Your analyzed pest images and AI results will appear here."
        />
      </Card>
    )
  }

  return (
    <div className="space-y-5">

      {/* HEADER */}
      <div>
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-green-soft" />

          <h2 className="text-xl font-bold text-forest">
            Pest Detection History
          </h2>
        </div>

        <p className="mt-1 text-sm text-forest-muted">
          Review your previous AI pest detection results,
          confidence scores and research methods.
        </p>
      </div>

      {/* STATISTICS */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">

        <StatCard
          icon={<Database className="h-5 w-5" />}
          label="Total Scans"
          value={stats.total}
        />

        <StatCard
          icon={<CheckCircle2 className="h-5 w-5" />}
          label="Known Pests"
          value={stats.known}
        />

        <StatCard
          icon={<ShieldAlert className="h-5 w-5" />}
          label="Unknown"
          value={stats.unknown}
        />

        <StatCard
          icon={<BarChart3 className="h-5 w-5" />}
          label="Avg. Confidence"
          value={`${(stats.average * 100).toFixed(1)}%`}
        />

      </div>

      {/* RESEARCH SUMMARY */}
      {stats.fineTuned > 0 && (
        <div className="flex items-center gap-3 rounded-2xl border border-green-soft/20 bg-green-soft/5 px-4 py-3">

          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-green-soft/10 text-green-soft">
            <BrainCircuit className="h-5 w-5" />
          </div>

          <div>
            <p className="text-xs font-bold text-forest">
              Adaptive Learning Activity
            </p>

            <p className="text-xs text-forest-muted">
              {stats.fineTuned} detection
              {stats.fineTuned !== 1 ? 's' : ''} used
              a selectively fine-tuned pest model.
            </p>
          </div>

        </div>
      )}

      {/* FILTER BAR */}
      <Card className="p-3">

        <div className="flex flex-col gap-3 md:flex-row">

          {/* SEARCH */}
          <div className="relative flex-1">

            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-forest-muted" />

            <input
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search pest or detection method..."
              className="w-full rounded-xl border border-beige bg-beige/20 py-2.5 pl-9 pr-3 text-sm text-forest outline-none transition focus:border-green-soft"
            />

          </div>

          {/* FILTERS */}
          <div className="flex gap-1 overflow-x-auto rounded-xl bg-beige p-1">

            <FilterButton
              active={filter === 'all'}
              onClick={() => setFilter('all')}
            >
              All
            </FilterButton>

            <FilterButton
              active={filter === 'known'}
              onClick={() => setFilter('known')}
            >
              Known
            </FilterButton>

            <FilterButton
              active={filter === 'unknown'}
              onClick={() => setFilter('unknown')}
            >
              Unknown
            </FilterButton>

            <FilterButton
              active={filter === 'fine_tuned'}
              onClick={() => setFilter('fine_tuned')}
            >
              Fine-Tuned
            </FilterButton>

          </div>

          {/* CLEAR */}
          <button
            type="button"
            onClick={() => setClearDialog(true)}
            className="rounded-xl px-3 py-2 text-xs font-semibold text-red-soft hover:bg-red-soft/10"
          >
            Clear History
          </button>

        </div>

      </Card>

      {/* TABLE */}
      {filteredEntries.length === 0 ? (
        <Card>
          <EmptyState
            title="No matching detections"
            description="Try another search or filter."
          />
        </Card>
      ) : (
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">

          <table className="w-full min-w-[950px] text-left text-sm">

            <thead className="border-b border-beige text-xs uppercase text-forest-muted">
              <tr>

                <th className="px-4 py-3">
                  Image
                </th>

                <th className="px-4 py-3">
                  Pest
                </th>

                <th className="px-4 py-3">
                  Date
                </th>

                <th className="px-4 py-3">
                  Confidence
                </th>

                <th className="px-4 py-3">
                  Status
                </th>

                <th className="px-4 py-3">
                  AI Method
                </th>

                <th className="px-4 py-3 text-right">
                  Action
                </th>

              </tr>
            </thead>

            <tbody>

              {filteredEntries.map((entry) => (

                <tr
                  key={entry.id}
                  onClick={() =>
                    setSelectedEntry(entry)
                  }
                  className="cursor-pointer border-b border-beige/60 transition last:border-0 hover:bg-beige/40"
                >

                  {/* IMAGE */}
                  <td className="px-4 py-3">

                    {entry.image_preview ? (
                      <img
                        src={entry.image_preview}
                        alt={entry.pest_name}
                        className="h-14 w-14 rounded-xl object-cover ring-1 ring-beige"
                      />
                    ) : (
                      <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-beige">
                        <ImageIcon className="h-5 w-5 text-forest-muted" />
                      </div>
                    )}

                  </td>

                  {/* PEST */}
                  <td className="px-4 py-3">

                    <p className="font-semibold capitalize text-forest">
                      {entry.pest_name.replace(
                        /_/g,
                        ' ',
                      )}
                    </p>

                    <p className="mt-0.5 text-[10px] text-forest-muted">
                      Click to view details
                    </p>

                  </td>

                  {/* DATE */}
                  <td className="px-4 py-3">

                    <div className="flex items-center gap-1.5 text-xs text-forest-light">
                      <CalendarDays className="h-3.5 w-3.5" />
                      {formatDate(entry.timestamp)}
                    </div>

                  </td>

                  {/* CONFIDENCE */}
                  <td className="px-4 py-3">

                    <span className="font-bold text-forest">
                      {formatConfidence(
                        entry.confidence,
                      )}
                    </span>

                  </td>

                  {/* STATUS */}
                  <td className="px-4 py-3">

                    <Badge
                      tone={
                        entry.is_ood
                          ? 'red'
                          : 'green'
                      }
                    >
                      {entry.is_ood
                        ? 'Unknown'
                        : 'Known'}
                    </Badge>

                  </td>

                  {/* METHOD */}
                  <td className="px-4 py-3">

                    <span className="rounded-lg bg-beige px-2.5 py-1.5 text-[10px] font-semibold text-forest-muted">
                      {sourceShortLabel(
                        entry.source,
                      )}
                    </span>

                  </td>

                  {/* DELETE */}
                  <td
                    className="px-4 py-3 text-right"
                    onClick={(event) =>
                      event.stopPropagation()
                    }
                  >

                    <button
                      type="button"
                      onClick={() =>
                        setPendingDelete(
                          entry.id,
                        )
                      }
                      className="rounded-lg p-2 text-red-soft transition hover:bg-red-soft/10"
                      title="Delete detection"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>
      )}

      {/* DETAIL MODAL */}
      {selectedEntry && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() =>
            setSelectedEntry(null)
          }
        >

          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl"
            onClick={(event) =>
              event.stopPropagation()
            }
          >

            <div className="flex items-start justify-between">

              <div>
                <p className="text-xs font-semibold uppercase text-forest-muted">
                  Detection Details
                </p>

                <h3 className="mt-1 text-xl font-bold capitalize text-forest">
                  {selectedEntry.pest_name.replace(
                    /_/g,
                    ' ',
                  )}
                </h3>
              </div>

              <button
                type="button"
                onClick={() =>
                  setSelectedEntry(null)
                }
                className="rounded-full p-2 text-forest-muted hover:bg-beige"
              >
                <X className="h-5 w-5" />
              </button>

            </div>

            {selectedEntry.image_preview && (
              <div className="mt-5 overflow-hidden rounded-xl bg-beige">
                <img
                  src={selectedEntry.image_preview}
                  alt={selectedEntry.pest_name}
                  className="max-h-[420px] w-full object-contain"
                />
              </div>
            )}

            <div className="mt-5 grid grid-cols-2 gap-3">

              <DetailItem
                label="Prediction"
                value={selectedEntry.pest_name.replace(
                  /_/g,
                  ' ',
                )}
              />

              <DetailItem
                label="Confidence"
                value={formatConfidence(
                  selectedEntry.confidence,
                )}
              />

              <DetailItem
                label="Status"
                value={
                  selectedEntry.is_ood
                    ? 'Unknown Pest'
                    : 'Known Pest'
                }
              />

              <DetailItem
                label="AI Method"
                value={sourceLabel(
                  selectedEntry.source,
                )}
              />

              <DetailItem
                label="Detected At"
                value={formatDate(
                  selectedEntry.timestamp,
                )}
              />

              <DetailItem
                label="Record ID"
                value={selectedEntry.id.slice(
                  0,
                  8,
                )}
              />

            </div>

          </div>

        </div>
      )}

      {/* DELETE DIALOG */}
      <ConfirmDialog
        isOpen={pendingDelete !== null}
        title="Delete pest detection"
        message="This detection will be permanently removed from your history."
        confirmLabel="Delete"
        danger
        loading={deleting}
        onConfirm={handleConfirmDelete}
        onCancel={() =>
          setPendingDelete(null)
        }
      />

      {/* CLEAR DIALOG */}
      <ConfirmDialog
        isOpen={clearDialog}
        title="Clear pest history"
        message="All your pest detection history will be permanently removed."
        confirmLabel="Clear History"
        danger
        onConfirm={handleClear}
        onCancel={() =>
          setClearDialog(false)
        }
      />

    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
}) {
  return (
    <Card className="p-4">

      <div className="flex items-center justify-between">

        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-green-soft/10 text-green-soft">
          {icon}
        </div>

        <Clock3 className="h-4 w-4 text-forest-muted" />

      </div>

      <p className="mt-4 text-xs text-forest-muted">
        {label}
      </p>

      <p className="mt-1 text-xl font-bold text-forest">
        {value}
      </p>

    </Card>
  )
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold transition ${
        active
          ? 'bg-white text-forest shadow-sm'
          : 'text-forest-muted hover:text-forest'
      }`}
    >
      {children}
    </button>
  )
}

function DetailItem({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl bg-beige/40 p-3">

      <p className="text-[10px] font-semibold uppercase text-forest-muted">
        {label}
      </p>

      <p className="mt-1 break-words text-sm font-semibold capitalize text-forest">
        {value}
      </p>

    </div>
  )
}