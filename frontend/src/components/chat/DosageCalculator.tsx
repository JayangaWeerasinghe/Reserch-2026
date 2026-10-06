import { useState } from 'react'
import { Calculator, Droplets, Ruler } from 'lucide-react'
import type { ChemicalEntry } from '@/lib/chatApi'
import { parseQuantity, midpoint, scaleRange, formatRange } from '@/lib/dosageCalc'

interface DosageCalculatorProps {
  chemicals: ChemicalEntry[]
}

type Mode = 'liters' | 'area'
type AreaUnit = 'acres' | 'hectares'

interface ChemicalResult {
  chemical: ChemicalEntry
  doseUnit: string
  canCalculate: boolean
  chemicalNeeded: ReturnType<typeof scaleRange> | null
  litersNeeded: number | null
  areaCovered: number | null
}

/** Computes one chemical's result from the SAME shared liters/area input every chemical below uses. */
function computeResult(
  chemical: ChemicalEntry,
  mode: Mode,
  areaUnit: AreaUnit,
  liters: number | null,
  area: number | null
): ChemicalResult {
  const doseRange = parseQuantity(chemical.dose_per_liter_water)
  const coverageRange = parseQuantity(
    areaUnit === 'acres' ? chemical.coverage_per_liter_mixture_acres : chemical.coverage_per_liter_mixture_hectares
  )
  const doseUnit = doseRange?.unit || 'units'
  const canCalculate = Boolean(doseRange || coverageRange)

  let chemicalNeeded: ReturnType<typeof scaleRange> | null = null
  let litersNeeded: number | null = null
  let areaCovered: number | null = null

  if (mode === 'liters') {
    if (liters !== null && liters > 0) {
      if (doseRange) chemicalNeeded = scaleRange(doseRange, liters)
      if (coverageRange) areaCovered = midpoint(coverageRange) * liters
    }
  } else if (area !== null && area > 0 && coverageRange) {
    const perLiter = midpoint(coverageRange)
    if (perLiter > 0) {
      litersNeeded = area / perLiter
      if (doseRange) chemicalNeeded = scaleRange(doseRange, litersNeeded)
    }
  }

  return { chemical, doseUnit, canCalculate, chemicalNeeded, litersNeeded, areaCovered }
}

/** Pure display row — no inputs of its own, everything comes from the shared calculator state above. */
function ChemicalResultRow({ result, mode, areaUnit }: { result: ChemicalResult; mode: Mode; areaUnit: AreaUnit }) {
  const unitLabel = areaUnit === 'acres' ? 'acres' : 'hectares'
  const { chemical, doseUnit, canCalculate, chemicalNeeded, litersNeeded, areaCovered } = result
  const hasResult = Boolean(chemicalNeeded) || litersNeeded !== null || areaCovered !== null

  return (
    <div className="p-3 border rounded-xl border-beige bg-white/70">
      <p className="text-sm font-bold text-forest">{chemical.name}</p>

      {!canCalculate ? (
        <p className="mt-1 text-xs text-forest-muted">Dosage/coverage not specified — can't calculate for this one.</p>
      ) : hasResult ? (
        <div className="px-3 py-2 mt-2 space-y-1 text-xs rounded-lg bg-amber-light/60">
          {chemicalNeeded && (
            <p className="flex items-center gap-1.5 font-semibold text-amber-dark">
              <Calculator className="h-3.5 w-3.5 shrink-0" />
              Use {formatRange(chemicalNeeded)} {doseUnit}
            </p>
          )}
          {mode === 'liters' && areaCovered !== null && (
            <p className="text-forest-muted">Covers approx. {formatRange(areaCovered)} {unitLabel}</p>
          )}
          {mode === 'area' && litersNeeded !== null && (
            <p className="text-forest-muted">Needs approx. {formatRange(litersNeeded)} L of mixture</p>
          )}
        </div>
      ) : (
        <p className="mt-1 text-xs text-forest-muted">Enter a value above to calculate.</p>
      )}
    </div>
  )
}

export default function DosageCalculator({ chemicals }: DosageCalculatorProps) {
  // Shared across every chemical below — enter it once, see all results update together.
  const [mode, setMode] = useState<Mode>('liters')
  const [areaUnit, setAreaUnit] = useState<AreaUnit>('acres')
  const [litersInput, setLitersInput] = useState('')
  const [areaInput, setAreaInput] = useState('')

  if (!chemicals || chemicals.length === 0) return null

  const parsedLiters = parseFloat(litersInput)
  const parsedArea = parseFloat(areaInput)
  const liters = litersInput.trim() !== '' && !Number.isNaN(parsedLiters) ? parsedLiters : null
  const area = areaInput.trim() !== '' && !Number.isNaN(parsedArea) ? parsedArea : null

  const results = chemicals.map((chemical) => computeResult(chemical, mode, areaUnit, liters, area))
  const anyCalculable = results.some((r) => r.canCalculate)

  return (
    <div className="mt-2 space-y-2.5 rounded-xl border border-amber/30 bg-amber-light/30 p-2.5">
      <p className="flex items-center gap-1.5 px-0.5 text-xs font-bold text-forest">
        <Calculator className="h-3.5 w-3.5" />
        Dosage Calculator
      </p>

      {/* Mode toggle — shared by every chemical listed below */}
      <div className="flex gap-1.5 rounded-lg bg-beige p-1">
        <button
          type="button"
          onClick={() => setMode('liters')}
          className={`flex flex-1 items-center justify-center gap-1 rounded-md py-1.5 text-xs font-semibold transition-colors ${
            mode === 'liters' ? 'bg-white text-forest shadow-sm' : 'text-forest-muted'
          }`}
        >
          <Droplets className="h-3.5 w-3.5" />
          By water (L)
        </button>
        <button
          type="button"
          onClick={() => setMode('area')}
          className={`flex flex-1 items-center justify-center gap-1 rounded-md py-1.5 text-xs font-semibold transition-colors ${
            mode === 'area' ? 'bg-white text-forest shadow-sm' : 'text-forest-muted'
          }`}
        >
          <Ruler className="h-3.5 w-3.5" />
          By field size
        </button>
      </div>

      {/* Single shared input, applied to every chemical in the results list below */}
      <div className="flex items-end gap-2">
        {mode === 'liters' ? (
          <div className="flex-1">
            <label className="mb-1 block text-[11px] font-medium text-forest-muted">Water/mixture (liters)</label>
            <input
              type="number"
              min="0"
              step="0.1"
              inputMode="decimal"
              value={litersInput}
              onChange={(e) => setLitersInput(e.target.value)}
              placeholder="e.g. 16"
              className="h-9 w-full rounded-lg border border-beige bg-beige px-2.5 text-sm text-forest outline-none focus:border-forest"
            />
          </div>
        ) : (
          <div className="flex-1">
            <label className="mb-1 block text-[11px] font-medium text-forest-muted">Field size</label>
            <input
              type="number"
              min="0"
              step="0.1"
              inputMode="decimal"
              value={areaInput}
              onChange={(e) => setAreaInput(e.target.value)}
              placeholder="e.g. 2"
              className="h-9 w-full rounded-lg border border-beige bg-beige px-2.5 text-sm text-forest outline-none focus:border-forest"
            />
          </div>
        )}

        <div className="shrink-0">
          <label className="mb-1 block text-[11px] font-medium text-forest-muted">Unit</label>
          <select
            value={areaUnit}
            onChange={(e) => setAreaUnit(e.target.value as AreaUnit)}
            className="px-2 text-sm border rounded-lg outline-none h-9 border-beige bg-beige text-forest focus:border-forest"
          >
            <option value="acres">acres</option>
            <option value="hectares">hectares</option>
          </select>
        </div>
      </div>

      {!anyCalculable && (
        <p className="px-0.5 text-xs text-forest-muted">
          Dosage/coverage wasn't specified for these chemicals — showing names only.
        </p>
      )}

      {/* One row per suggested chemical — all driven by the single input above */}
      <div className="space-y-2">
        {results.map((result, i) => (
          <ChemicalResultRow key={`${result.chemical.name}-${i}`} result={result} mode={mode} areaUnit={areaUnit} />
        ))}
      </div>
    </div>
  )
}