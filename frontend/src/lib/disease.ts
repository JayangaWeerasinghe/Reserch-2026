export interface DiseaseInfo {
  en: string
  si: string
  color: string
}

const DISEASE_TABLE: Record<string, DiseaseInfo> = {
  'bacterial blight': { en: 'Bacterial Blight', si: 'බැක්ටීරියා අංගමාරය', color: '#E74C3C' },
  'leaf blast': { en: 'Leaf Blast', si: 'කොල පාළු රෝගය', color: '#F4991A' },
  'brown spot': { en: 'Brown Spot', si: 'දුඹුරු පුල්ලි රෝගය', color: '#8B4513' },
  healthy: { en: 'Healthy', si: 'නීරෝගී', color: '#27AE60' },
}

/** Backend disease names arrive as either "Bacterial_Blight" or "Bacterial Blight" — normalize both. */
function normalize(name: string): string {
  return name.replace(/_/g, ' ').trim().toLowerCase()
}

export function getDiseaseInfo(name: string | null | undefined): DiseaseInfo {
  if (!name) return { en: 'Unknown', si: 'නොදන්නා', color: '#64748B' }
  const key = normalize(name)
  return DISEASE_TABLE[key] || { en: name, si: name, color: '#64748B' }
}

export function diseaseColor(name: string | null | undefined): string {
  return getDiseaseInfo(name).color
}

export function diseaseSinhalaName(name: string | null | undefined): string {
  return getDiseaseInfo(name).si
}

export function severityLabel(percentage: number | null | undefined): { label: string; color: string } {
  if (percentage == null) return { label: 'N/A', color: '#64748B' }
  if (percentage < 10) return { label: 'Low', color: '#27AE60' }
  if (percentage < 30) return { label: 'Moderate', color: '#F4991A' }
  return { label: 'Severe', color: '#E74C3C' }
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('en-LK', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
