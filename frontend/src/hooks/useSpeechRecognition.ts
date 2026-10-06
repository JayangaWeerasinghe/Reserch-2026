import { useCallback, useEffect, useRef, useState } from 'react'
import type { SpeechRecognitionLike } from '@/types/speech'

export type MicLang = 'en-US' | 'si-LK'

interface UseSpeechRecognitionResult {
  supported: boolean
  listening: boolean
  interimTranscript: string
  error: string | null
  start: (lang: MicLang) => void
  stop: () => void
}

function getRecognitionCtor() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

/**
 * Browser-native voice input. `onFinalResult` fires once per finalized
 * phrase — the caller decides how to merge it into their text state.
 */
export function useSpeechRecognition(onFinalResult: (text: string) => void): UseSpeechRecognitionResult {
  const [listening, setListening] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const onFinalRef = useRef(onFinalResult)
  onFinalRef.current = onFinalResult

  const supported = Boolean(getRecognitionCtor())

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop()
    }
  }, [])

  const start = useCallback((lang: MicLang) => {
    const Ctor = getRecognitionCtor()
    if (!Ctor) {
      setError('Voice input is not supported in this browser. Try Chrome or Edge.')
      return
    }
    setError(null)
    setInterimTranscript('')

    const recognition = new Ctor()
    recognition.lang = lang
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) final += transcript
        else interim += transcript
      }
      setInterimTranscript(interim)
      if (final.trim()) onFinalRef.current(final.trim())
    }
    recognition.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') {
        setError(null)
      } else if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setError('Microphone permission denied. | මයික්‍රෆෝන් අවසර ලබා දී නැත.')
      } else if (event.error === 'language-not-supported') {
        setError(
          lang === 'si-LK'
            ? 'This browser cannot recognize Sinhala speech. Try Chrome, or switch to English.'
            : 'Voice input language is not supported by this browser.'
        )
      } else {
        setError('Voice input failed. Please try again.')
      }
    }
    recognition.onend = () => {
      setListening(false)
      setInterimTranscript('')
    }

    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }, [])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  return { supported, listening, interimTranscript, error, start, stop }
}
