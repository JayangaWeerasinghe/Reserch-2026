import { useEffect, useRef, useState } from 'react'
import { registerAudio } from '@/lib/audioPlayer'

export type SpeechStatus = 'idle' | 'playing' | 'paused'

export function useSpeechAudio(base64?: string | null) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [status, setStatus] = useState<SpeechStatus>('idle')

  // Reset when the underlying clip changes (e.g. new diagnosis result)
  useEffect(() => {
    audioRef.current?.pause()
    audioRef.current = null
    setStatus('idle')
  }, [base64])

  // Stop playback if the component unmounts mid-clip
  useEffect(() => {
    return () => {
      audioRef.current?.pause()
    }
  }, [])

  function ensureAudio(): HTMLAudioElement | null {
    if (!base64) return null
    if (!audioRef.current) {
      const audio = new Audio(`data:audio/mp3;base64,${base64}`)
      audio.addEventListener('ended', () => setStatus('idle'))
      audioRef.current = audio
    }
    return audioRef.current
  }

  function play() {
    const audio = ensureAudio()
    if (!audio) return
    registerAudio(audio)
    if (audio.ended || status === 'idle') audio.currentTime = 0
    audio.play().then(() => setStatus('playing')).catch(() => {})
  }

  function pause() {
    audioRef.current?.pause()
    setStatus('paused')
  }

  function stop() {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    setStatus('idle')
  }

  return { status, play, pause, stop }
}
