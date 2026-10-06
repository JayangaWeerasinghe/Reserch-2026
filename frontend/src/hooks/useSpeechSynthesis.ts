import { useCallback, useEffect, useRef, useState } from 'react'

interface UseSpeechSynthesisResult {
  supported: boolean
  speakingId: string | null
  speak: (id: string, text: string, lang: 'en' | 'si') => void
  stop: () => void
  hasNativeVoice: (lang: 'en' | 'si') => boolean
}

function pickVoice(lang: 'en' | 'si'): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices()
  return voices.find((v) => v.lang.toLowerCase().startsWith(lang)) || voices.find((v) => v.lang.toLowerCase().startsWith('en'))
}

function findNativeVoice(lang: 'en' | 'si'): SpeechSynthesisVoice | undefined {
  return window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang))
}

/** Browser-native voice output. Only one message speaks at a time — starting a new one cancels the previous. */
export function useSpeechSynthesis(): UseSpeechSynthesisResult {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const [speakingId, setSpeakingId] = useState<string | null>(null)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  useEffect(() => {
    if (!supported) return
    // Chrome loads voices asynchronously — warm the cache so the first speak() call has options.
    window.speechSynthesis.getVoices()
    return () => {
      window.speechSynthesis.cancel()
    }
  }, [supported])

  const stop = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeakingId(null)
  }, [supported])

  const speak = useCallback(
    (id: string, text: string, lang: 'en' | 'si') => {
      if (!supported || !text.trim()) return
      window.speechSynthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(text)
      const voice = pickVoice(lang)
      if (voice) utterance.voice = voice
      utterance.lang = voice?.lang || (lang === 'si' ? 'si-LK' : 'en-US')
      utterance.rate = 0.98
      utterance.onend = () => setSpeakingId((current) => (current === id ? null : current))
      utterance.onerror = () => setSpeakingId((current) => (current === id ? null : current))

      utteranceRef.current = utterance
      setSpeakingId(id)
      window.speechSynthesis.speak(utterance)
    },
    [supported]
  )

  const hasNativeVoice = useCallback(
    (lang: 'en' | 'si') => {
      if (!supported) return false
      return Boolean(findNativeVoice(lang))
    },
    [supported]
  )

  return { supported, speakingId, speak, stop, hasNativeVoice }
}
