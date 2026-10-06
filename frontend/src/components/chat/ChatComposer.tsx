import { useRef } from 'react'
import type { ChangeEvent, KeyboardEvent } from 'react'
import { SendHorizontal, Mic, MicOff } from 'lucide-react'
import type { MicLang } from '@/hooks/useSpeechRecognition'

interface ChatComposerProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled?: boolean
  micSupported: boolean
  listening: boolean
  interimText: string
  onMicToggle: () => void
  micLang: MicLang
  onToggleMicLang: () => void
}

export default function ChatComposer({
  value,
  onChange,
  onSend,
  disabled,
  micSupported,
  listening,
  interimText,
  onMicToggle,
  micLang,
  onToggleMicLang,
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !disabled) onSend()
    }
  }

  function handleChange(e: ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value)
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`
    }
  }

  return (
    <div className="space-y-1.5">
      {listening && (
        <p className="px-2 text-xs italic text-forest-muted">
          {interimText || 'Listening… speak now'}
        </p>
      )}

      <div className="flex items-end gap-2 rounded-2xl border border-beige bg-white p-2 shadow-sm">
        {micSupported && (
          <button
            onClick={onToggleMicLang}
            disabled={listening}
            title="Voice input language"
            className="flex h-10 shrink-0 items-center justify-center rounded-xl border border-beige px-2 text-xs font-bold text-forest-muted transition-colors hover:border-forest-muted disabled:opacity-50"
          >
            {micLang === 'si-LK' ? 'සිං' : 'EN'}
          </button>
        )}

        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder="ප්‍රශ්නයක් අසන්න | Ask about a rice disease or pest..."
          className="font-sinhala max-h-[120px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-forest placeholder:text-forest-muted/60 focus:outline-none disabled:opacity-60"
        />

        {micSupported && (
          <button
            onClick={onMicToggle}
            disabled={disabled}
            aria-label={listening ? 'Stop voice input' : 'Start voice input'}
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-all active:scale-95 disabled:opacity-50 ${
              listening ? 'animate-pulse-mic bg-red-soft text-white' : 'bg-beige text-forest hover:bg-beige/70'
            }`}
          >
            {listening ? <MicOff className="h-[18px] w-[18px]" /> : <Mic className="h-[18px] w-[18px]" />}
          </button>
        )}

        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber text-white transition-all hover:bg-amber-dark active:scale-95 disabled:bg-amber/40"
        >
          <SendHorizontal className="h-[18px] w-[18px]" />
        </button>
      </div>
    </div>
  )
}
