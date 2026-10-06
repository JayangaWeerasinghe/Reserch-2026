import { Sprout, User, MessageCircleQuestion, Volume2, Square } from 'lucide-react'
import type { ChatMessage } from '@/store/chatStore'
import { renderLiteMarkdown, stripLiteMarkdown } from '@/lib/markdownLite'
import DosageCalculator from './DosageCalculator'

interface ChatBubbleProps {
  message: ChatMessage
  onAskFollowUp?: (question: string) => void
  ttsSupported?: boolean
  speaking?: boolean
  onToggleSpeak?: () => void
}

export default function ChatBubble({
  message,
  onAskFollowUp,
  ttsSupported,
  speaking,
  onToggleSpeak,
}: ChatBubbleProps) {
  const isUser = message.role === 'user'
  const canSpeak = !isUser && ttsSupported && onToggleSpeak && stripLiteMarkdown(message.content).length > 0

  return (
    <div className={`flex items-start gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? 'bg-forest' : 'bg-amber'
        }`}
      >
        {isUser ? <User className="w-4 h-4 text-white" /> : <Sprout className="w-4 h-4 text-white" />}
      </div>

      <div className={`flex max-w-[85%] flex-col gap-1.5 sm:max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm shadow-sm ${
            isUser
              ? 'rounded-tr-sm bg-forest text-white'
              : message.inScope === false
                ? 'rounded-tl-sm border border-red-soft/30 bg-red-soft/10 text-forest'
                : 'rounded-tl-sm bg-white text-forest'
          }`}
        >
          {isUser ? <p className="leading-relaxed">{message.content}</p> : renderLiteMarkdown(message.content)}
        </div>

        {!isUser && message.chemicals && message.chemicals.length > 0 && (
          <div className="w-full">
            <DosageCalculator chemicals={message.chemicals} />
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {!isUser && message.followUpQuestion && onAskFollowUp && (
            <button
              onClick={() => onAskFollowUp(message.followUpQuestion as string)}
              className="flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber-light px-3 py-1.5 text-xs font-medium text-amber-dark transition-colors hover:bg-amber/20"
            >
              <MessageCircleQuestion className="h-3.5 w-3.5 shrink-0" />
              <span>{message.followUpQuestion}</span>
            </button>
          )}

          {canSpeak && (
            <button
              onClick={onToggleSpeak}
              aria-label={speaking ? 'Stop reading aloud' : 'Read reply aloud'}
              className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                speaking
                  ? 'border-forest bg-forest text-white'
                  : 'border-beige bg-white text-forest-muted hover:border-forest-muted'
              }`}
            >
              {speaking ? <Square className="w-3 h-3" /> : <Volume2 className="h-3.5 w-3.5" />}
              {speaking ? 'Stop' : 'Listen'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}