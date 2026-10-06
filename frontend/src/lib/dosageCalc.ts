/**
 * Parses free-text dose/coverage strings coming back from the treatment
 * chatbot, e.g.:
 *   "Approx. 2-3 g per L water"   -> { min: 2, max: 3, unit: "g" }
 *   "Approx. 1-2 ml per L water"  -> { min: 1, max: 2, unit: "ml" }
 *   "Approx. 1 acres"             -> { min: 1, max: 1, unit: "acres" }
 *   "Approx. 0.4 hectares"        -> { min: 0.4, max: 0.4, unit: "hectares" }
 *   "Not specified per 1L water"  -> null
 */
export interface QuantityRange {
  min: number
  max: number
  unit: string
}

const NUMBER_RANGE_RE = /(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)/

export function parseQuantity(text: string | undefined | null): QuantityRange | null {
  if (!text) return null

  const lower = text.toLowerCase()
  if (lower.includes('not specified') || lower.includes('n/a') || !lower.trim()) {
    return null
  }

  const match = text.match(NUMBER_RANGE_RE)
  if (!match) return null

  let min: number
  let max: number
  if (match[1] !== undefined && match[2] !== undefined) {
    min = parseFloat(match[1])
    max = parseFloat(match[2])
  } else {
    min = max = parseFloat(match[3])
  }

  // Unit = the first alphabetic token right after the matched number(s),
  // e.g. "g" out of "g per L water", or "acres" out of "acres".
  const afterMatch = text.slice((match.index ?? 0) + match[0].length).trim()
  const unitMatch = afterMatch.match(/^([a-zA-Z]+)/)
  const unit = unitMatch ? unitMatch[1] : ''

  return { min, max, unit }
}

/** Midpoint of a range — used as the "typical" per-liter/per-area rate. */
export function midpoint(range: QuantityRange): number {
  return (range.min + range.max) / 2
}

/** Scales a parsed dose/coverage range by a factor (liters, hectares, etc). */
export function scaleRange(range: QuantityRange, factor: number): { min: number; max: number } {
  return { min: range.min * factor, max: range.max * factor }
}

/** Formats a plain number or a {min,max} range into a short, rounded display string. */
export function formatRange(value: number | { min: number; max: number }): string {
  const round = (n: number): string => {
    if (n === 0) return '0'
    if (n >= 100) return Math.round(n).toString()
    if (n >= 10) return (Math.round(n * 10) / 10).toString()
    return (Math.round(n * 100) / 100).toString()
  }

  if (typeof value === 'number') {
    return round(value)
  }

  const { min, max } = value
  if (Math.abs(max - min) < 0.001) {
    return round(min)
  }
  return `${round(min)}–${round(max)}`
}