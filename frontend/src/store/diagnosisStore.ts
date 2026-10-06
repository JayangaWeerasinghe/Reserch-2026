import { create } from 'zustand'
import type { AnalyzeResult } from '@/lib/leafApi'

export interface VoiceHistoryEntry {
  id: string
  timestamp: string
  disease: string
  confidence: number
  is_ood: boolean
  sinhala_transcript: string
  english_translation: string
  all_scores: Record<string, number>
  userId: string
}

export interface PestHistoryEntry {
  id: string
  timestamp: string
  pest_name: string
  confidence: number
  is_ood: boolean
  userId: string

  // Compressed thumbnail of the analyzed image.
  image_preview?: string

  // base_model | ood | few_shot | fine_tuned | quality_check
  source?: string
}

const HISTORY_KEY = 'paddyguard_diagnosis_history'
const MAX_ENTRIES = 50

interface StoredHistory {
  voiceHistory: VoiceHistoryEntry[]
  pestHistory: PestHistoryEntry[]
}

function loadHistory(): StoredHistory {
  const raw = localStorage.getItem(HISTORY_KEY)

  if (!raw) {
    return {
      voiceHistory: [],
      pestHistory: [],
    }
  }

  try {
    const parsed = JSON.parse(raw)

    return {
      voiceHistory: Array.isArray(parsed.voiceHistory)
        ? parsed.voiceHistory
        : [],

      pestHistory: Array.isArray(parsed.pestHistory)
        ? parsed.pestHistory
        : [],
    }
  } catch {
    return {
      voiceHistory: [],
      pestHistory: [],
    }
  }
}

function persist(
  voiceHistory: VoiceHistoryEntry[],
  pestHistory: PestHistoryEntry[],
) {
  localStorage.setItem(
    HISTORY_KEY,
    JSON.stringify({
      voiceHistory,
      pestHistory,
    }),
  )
}

interface DiagnosisState {
  voiceHistory: VoiceHistoryEntry[]
  pestHistory: PestHistoryEntry[]
  leafResult: AnalyzeResult | null

  addVoiceEntry: (
    entry: Omit<VoiceHistoryEntry, 'id' | 'timestamp'>
  ) => void

  addPestEntry: (
    entry: Omit<PestHistoryEntry, 'id' | 'timestamp'>
  ) => void

  deleteVoiceEntry: (id: string) => void

  clearVoiceHistory: (userId: string) => void

  deletePestEntry: (id: string) => void

  clearPestHistory: (userId: string) => void

  setLeafResult: (result: AnalyzeResult | null) => void

  historyForUser: (
    userId: string
  ) => {
    voice: VoiceHistoryEntry[]
    pest: PestHistoryEntry[]
  }
}

export const useDiagnosisStore = create<DiagnosisState>((set, get) => ({
  ...loadHistory(),

  leafResult: null,

  addVoiceEntry: (entry) => {
    const full: VoiceHistoryEntry = {
      ...entry,
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    }

    const voiceHistory = [
      full,
      ...get().voiceHistory,
    ].slice(0, MAX_ENTRIES)

    persist(
      voiceHistory,
      get().pestHistory,
    )

    set({
      voiceHistory,
    })
  },

  addPestEntry: (entry) => {
    const full: PestHistoryEntry = {
      ...entry,
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    }

    const pestHistory = [
      full,
      ...get().pestHistory,
    ].slice(0, MAX_ENTRIES)

    persist(
      get().voiceHistory,
      pestHistory,
    )

    set({
      pestHistory,
    })
  },

  deleteVoiceEntry: (id) => {
    const voiceHistory = get().voiceHistory.filter(
      (entry) => entry.id !== id,
    )

    persist(
      voiceHistory,
      get().pestHistory,
    )

    set({
      voiceHistory,
    })
  },

  clearVoiceHistory: (userId) => {
    const voiceHistory = get().voiceHistory.filter(
      (entry) => entry.userId !== userId,
    )

    persist(
      voiceHistory,
      get().pestHistory,
    )

    set({
      voiceHistory,
    })
  },

  deletePestEntry: (id) => {
    const pestHistory = get().pestHistory.filter(
      (entry) => entry.id !== id,
    )

    persist(
      get().voiceHistory,
      pestHistory,
    )

    set({
      pestHistory,
    })
  },

  clearPestHistory: (userId) => {
    const pestHistory = get().pestHistory.filter(
      (entry) => entry.userId !== userId,
    )

    persist(
      get().voiceHistory,
      pestHistory,
    )

    set({
      pestHistory,
    })
  },

  setLeafResult: (result) => {
    set({
      leafResult: result,
    })
  },

  historyForUser: (userId) => ({
    voice: get().voiceHistory.filter(
      (entry) => entry.userId === userId,
    ),

    pest: get().pestHistory.filter(
      (entry) => entry.userId === userId,
    ),
  }),
}))