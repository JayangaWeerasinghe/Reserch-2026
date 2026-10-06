import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import { useLocation, useNavigate } from 'react-router-dom'

import {
  Clock,
  MessageCircle,
  Play,
  RotateCcw,
  Sprout,
  Volume2,
  VolumeX,
} from 'lucide-react'

import toast from 'react-hot-toast'

import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmDialog from '@/components/ui/ConfirmDialog'

import ChatBubble from '@/components/chat/ChatBubble'
import ChatComposer from '@/components/chat/ChatComposer'
import TopicChips from '@/components/chat/TopicChips'
import TypingIndicator from '@/components/chat/TypingIndicator'

import {
  sendChatMessage,
  getChatTopics,
  clearChatSession,
} from '@/lib/chatApi'

import { stripLiteMarkdown } from '@/lib/markdownLite'

import {
  useChatStore,
  type ArchivedChat,
} from '@/store/chatStore'

import { useAuthStore } from '@/store/authStore'

import {
  useSpeechRecognition,
} from '@/hooks/useSpeechRecognition'

import type {
  MicLang,
} from '@/hooks/useSpeechRecognition'

import {
  useSpeechSynthesis,
} from '@/hooks/useSpeechSynthesis'

import { formatDate } from '@/lib/disease'

type Tab = 'chat' | 'history'

type SpeechLanguage = 'en' | 'si'

const EMPTY_HISTORY: ArchivedChat[] = []

function normalizeSpeechLanguage(
  language: unknown
): SpeechLanguage {
  if (
    language === 'si' ||
    language === 'si-LK'
  ) {
    return 'si'
  }

  return 'en'
}

function chatPreview(
  messages: {
    role: 'user' | 'assistant'
    content: string
  }[]
): string {
  const firstUserMessage =
    messages.find(
      (message) =>
        message.role === 'user'
    )

  return (
    firstUserMessage?.content ||
    'Conversation'
  )
}

export default function TreatmentChat() {
  /*
   * ==================================================
   * AUTH
   * ==================================================
   */

  const user = useAuthStore(
    (state) => state.user
  )

  const userId =
    user?.id || 'guest'

  /*
   * ==================================================
   * NAVIGATION
   *
   * Leaf/Pest result pages can deep-link here with an
   * initial message to auto-send (e.g. "Bacterial Blight"
   * from the "Ask Treatment Advisor" button), passed via
   * router state: navigate('/chat', { state: { initialMessage } }).
   * ==================================================
   */

  const location = useLocation()
  const navigate = useNavigate()

  /*
   * ==================================================
   * CHAT STORE
   * ==================================================
   */

  const session = useChatStore(
    (state) =>
      state.sessions[userId]
  )

  const startNewSession =
    useChatStore(
      (state) =>
        state.startNewSession
    )

  const addMessage =
    useChatStore(
      (state) =>
        state.addMessage
    )

  const resetSession =
    useChatStore(
      (state) =>
        state.resetSession
    )

  const continueSession =
    useChatStore(
      (state) =>
        state.continueSession
    )

  const archivedChats =
    useChatStore(
      (state) =>
        state.history[userId] ??
        EMPTY_HISTORY
    )

  /*
   * ==================================================
   * LOCAL STATE
   * ==================================================
   */

  const [tab, setTab] =
    useState<Tab>('chat')

  const [
    selectedChat,
    setSelectedChat,
  ] =
    useState<ArchivedChat | null>(
      null
    )

  const [input, setInput] =
    useState('')

  const [sending, setSending] =
    useState(false)

  const [topics, setTopics] =
    useState<string[]>([])

  const [
    confirmReset,
    setConfirmReset,
  ] =
    useState(false)

  const [
    resetting,
    setResetting,
  ] =
    useState(false)

  const [micLang, setMicLang] =
    useState<MicLang>('en-US')

  const [
    autoSpeak,
    setAutoSpeak,
  ] =
    useState(false)

  /*
   * ==================================================
   * REFS
   * ==================================================
   */

  const scrollRef =
    useRef<HTMLDivElement>(null)

  const autoSpeakRef =
    useRef(autoSpeak)

  const warnedNoSinhalaVoiceRef =
    useRef(false)

  /*
   * Prevent duplicate initialization.
   *
   * React StrictMode can execute effects twice
   * during development.
   */

  const initializedUserRef =
    useRef<string | null>(null)

  autoSpeakRef.current =
    autoSpeak

  /*
   * ==================================================
   * SPEECH SYNTHESIS
   * ==================================================
   */

  const tts =
    useSpeechSynthesis()

  /*
   * ==================================================
   * SPEECH RECOGNITION
   * ==================================================
   */

  const handleSpeechResult =
    useCallback(
      (finalText: string) => {
        setInput(
          (previous) =>
            previous
              ? `${previous} ${finalText}`
              : finalText
        )
      },
      []
    )

  const recognition =
    useSpeechRecognition(
      handleSpeechResult
    )

  /*
   * ==================================================
   * SEND MESSAGE
   *
   * Declared before the init effect below (function
   * declarations are hoisted) so a deep-linked initial
   * message can be sent as soon as the fresh session is
   * ready.
   * ==================================================
   */

  async function handleSend(
    text?: string
  ): Promise<void> {
    const content = (
      text ?? input
    ).trim()

    if (
      !content ||
      sending
    ) {
      return
    }

    /*
     * Always retrieve the latest session.
     *
     * This is important after clicking Continue,
     * because the sessionId may have changed.
     */

    const currentSession =
      useChatStore
        .getState()
        .sessions[userId]

    if (!currentSession) {
      toast.error(
        'Chat session is not ready. Please try again.'
      )

      return
    }

    /*
     * Stop microphone.
     */

    if (
      recognition.listening
    ) {
      recognition.stop()
    }

    /*
     * Stop current TTS.
     */

    tts.stop()

    /*
     * Save user message locally.
     */

    addMessage(userId, {
      role: 'user',
      content,
    })

    setInput('')
    setSending(true)

    try {
      /*
       * Send using current session ID.
       *
       * For a restored History conversation this is
       * the ORIGINAL session ID.
       */

      const response =
        await sendChatMessage(
          content,
          currentSession.sessionId
        )

      const language =
        normalizeSpeechLanguage(
          response.language
        )

      /*
       * Save assistant response.
       */

      const assistantMessage =
        addMessage(userId, {
          role: 'assistant',
          content:
            response.reply,
          language,
          inScope:
            response.in_scope,
          chemicals:
            response.chemicals,
          followUpQuestion:
            response.follow_up_question,
        })

      /*
       * Automatically read assistant response
       * when enabled.
       */

      if (
        autoSpeakRef.current
      ) {
        speakMessage(
          assistantMessage.id,
          stripLiteMarkdown(
            response.reply
          ),
          language
        )
      }
    } catch (
      error: unknown
    ) {
      let errorMessage =
        'Could not reach the treatment advisor. Please try again.'

      /*
       * Read API error detail.
       */

      if (
        typeof error ===
          'object' &&
        error !== null &&
        'response' in error
      ) {
        const responseError =
          error as {
            response?: {
              data?: {
                detail?: unknown
              }
            }
          }

        const detail =
          responseError
            .response?.data
            ?.detail

        if (
          typeof detail ===
          'string'
        ) {
          errorMessage =
            detail
        }
      }

      toast.error(
        errorMessage
      )

      /*
       * Add error message to chat.
       */

      addMessage(userId, {
        role: 'assistant',
        content:
          "⚠️ Sorry, I couldn't process that right now. Please check your connection and try again. | " +
          'සමාවන්න, දැනට එය සැකසිය නොහැක. නැවත උත්සාහ කරන්න.',
        inScope: true,
        language: 'en',
      })
    } finally {
      setSending(false)
    }
  }

  /*
   * ==================================================
   * INITIALIZE NEW CHAT
   *
   * Every time TreatmentChat is opened for a user,
   * start with a fresh conversation.
   *
   * Existing conversation is archived first.
   *
   * If a deep link brought an initialMessage (e.g. from
   * the Leaf/Pest "Ask Treatment Advisor" button), send
   * it immediately in this fresh session, then clear the
   * router state so refreshing/revisiting doesn't resend.
   * ==================================================
   */

  useEffect(() => {
    if (
      initializedUserRef.current ===
      userId
    ) {
      return
    }

    initializedUserRef.current =
      userId

    startNewSession(userId)

    setTab('chat')
    setSelectedChat(null)
    setInput('')
    setSending(false)

    const initialMessage = (
      location.state as
        | { initialMessage?: string }
        | null
    )?.initialMessage

    if (initialMessage) {
      navigate(location.pathname, {
        replace: true,
        state: {},
      })

      void handleSend(initialMessage)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    userId,
    startNewSession,
  ])

  /*
   * ==================================================
   * SPEAK MESSAGE
   * ==================================================
   */

  function speakMessage(
    id: string,
    text: string,
    language: SpeechLanguage
  ): void {
    if (
      language === 'si' &&
      !tts.hasNativeVoice('si') &&
      !warnedNoSinhalaVoiceRef.current
    ) {
      warnedNoSinhalaVoiceRef.current =
        true

      toast(
        'No Sinhala voice found on this device — reading with an English voice instead.',
        {
          icon: 'ℹ️',
        }
      )
    }

    tts.speak(
      id,
      text,
      language
    )
  }

  /*
   * ==================================================
   * LOAD TOPICS
   * ==================================================
   */

  useEffect(() => {
    let active = true

    getChatTopics()
      .then((result) => {
        if (!active) {
          return
        }

        setTopics(
          Array.isArray(result)
            ? result
            : []
        )
      })
      .catch(() => {
        if (active) {
          setTopics([])
        }
      })

    return () => {
      active = false
    }
  }, [])

  /*
   * ==================================================
   * AUTO SCROLL
   * ==================================================
   */

  useEffect(() => {
    if (!session) {
      return
    }

    const element =
      scrollRef.current

    if (!element) {
      return
    }

    element.scrollTo({
      top: element.scrollHeight,
      behavior: 'smooth',
    })
  }, [
    session?.messages.length,
    sending,
  ])

  /*
   * ==================================================
   * SPEECH ERROR
   * ==================================================
   */

  useEffect(() => {
    if (recognition.error) {
      toast.error(
        recognition.error
      )
    }
  }, [
    recognition.error,
  ])

  /*
   * ==================================================
   * MICROPHONE
   * ==================================================
   */

  function handleMicToggle(): void {
    if (
      recognition.listening
    ) {
      recognition.stop()
      return
    }

    tts.stop()

    recognition.start(
      micLang
    )
  }

  function handleToggleMicLang(): void {
    setMicLang(
      (language) =>
        language ===
        'en-US'
          ? 'si-LK'
          : 'en-US'
    )
  }

  /*
   * ==================================================
   * CONTINUE HISTORY CHAT
   *
   * Restores the ORIGINAL sessionId.
   *
   * This means the backend can continue the same
   * conversation instead of creating a new one.
   * ==================================================
   */

  function handleContinueChat(
    archived: ArchivedChat
  ): void {
    tts.stop()

    if (
      recognition.listening
    ) {
      recognition.stop()
    }

    continueSession(
      userId,
      archived
    )

    setTab('chat')
    setSelectedChat(null)
    setInput('')
    setSending(false)

    toast.success(
      'Conversation restored. You can continue chatting.'
    )
  }

  /*
   * ==================================================
   * CONFIRM NEW CHAT
   * ==================================================
   */

  async function handleConfirmReset(): Promise<void> {
    if (!session) {
      setConfirmReset(false)
      return
    }

    setResetting(true)

    /*
     * Stop speech.
     */

    tts.stop()

    /*
     * Stop microphone.
     */

    if (
      recognition.listening
    ) {
      recognition.stop()
    }

    try {
      /*
       * Clear backend conversation.
       *
       * This does NOT affect local History because
       * the local history is handled by resetSession.
       */

      await clearChatSession(
        session.sessionId
      )
    } catch {
      /*
       * Backend cleanup is non-fatal.
       */
    } finally {
      /*
       * Archive current chat and create new session.
       */

      resetSession(userId)

      setInput('')
      setSending(false)
      setSelectedChat(null)
      setTab('chat')

      setResetting(false)
      setConfirmReset(false)
    }
  }

  /*
   * ==================================================
   * LOADING STATE
   * ==================================================
   */

  if (!session) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-7.5rem)]">
        <div className="text-sm text-forest-muted">
          Starting a new treatment chat...
        </div>
      </div>
    )
  }

  const hasMessages =
    session.messages.length >
    0

  /*
   * ==================================================
   * UI
   * ==================================================
   */

  return (
    <div className="mx-auto flex h-[calc(100vh-7.5rem)] max-w-3xl flex-col">

      {/* ============================================
          HEADER
          ============================================ */}

      <div className="flex items-center justify-between gap-2 mb-3">

        <div className="min-w-0">

          <h2 className="text-lg font-bold truncate font-sinhala text-forest">
            ප්‍රතිකාර උපදේශක | Treatment Advisor
          </h2>

          <p className="text-xs truncate text-forest-muted">
            Ask about rice leaf diseases and pests
            — in English or Sinhala
          </p>

        </div>

        {tab === 'chat' && (
          <div className="flex items-center gap-2 shrink-0">

            {/* TTS toggle */}

            {tts.supported && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (
                    autoSpeak
                  ) {
                    tts.stop()
                  }

                  setAutoSpeak(
                    (value) =>
                      !value
                  )
                }}
                title={
                  autoSpeak
                    ? 'Auto-read replies: on'
                    : 'Auto-read replies: off'
                }
              >
                {autoSpeak ? (
                  <Volume2 className="h-3.5 w-3.5" />
                ) : (
                  <VolumeX className="h-3.5 w-3.5" />
                )}
              </Button>
            )}

            {/* New chat */}

            {hasMessages && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setConfirmReset(
                    true
                  )
                }
              >
                <RotateCcw className="h-3.5 w-3.5" />

                New chat
              </Button>
            )}

          </div>
        )}

      </div>

      {/* ============================================
          TAB NAVIGATION
          ============================================ */}

      <div className="flex gap-2 p-1 mb-3 rounded-xl bg-beige">

        <button
          type="button"
          onClick={() =>
            setTab('chat')
          }
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-semibold transition-colors ${
            tab === 'chat'
              ? 'bg-white text-forest shadow-sm'
              : 'text-forest-muted'
          }`}
        >
          <MessageCircle className="w-4 h-4" />

          Chat
        </button>

        <button
          type="button"
          onClick={() =>
            setTab('history')
          }
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-semibold transition-colors ${
            tab === 'history'
              ? 'bg-white text-forest shadow-sm'
              : 'text-forest-muted'
          }`}
        >
          <Clock className="w-4 h-4" />

          History

          {archivedChats.length >
            0 && (
            <span className="ml-1 text-xs">
              (
              {
                archivedChats.length
              }
              )
            </span>
          )}

        </button>

      </div>

      {/* ============================================
          CHAT TAB
          ============================================ */}

      {tab === 'chat' ? (
        <>
          <div
            ref={scrollRef}
            className="flex-1 p-4 space-y-4 overflow-y-auto rounded-2xl bg-beige/40"
          >

            {!hasMessages ? (

              <div className="flex flex-col items-center justify-center h-full gap-5 px-4 text-center">

                <div className="flex items-center justify-center w-16 h-16 rounded-full bg-amber">
                  <Sprout className="w-8 h-8 text-white" />
                </div>

                <div>

                  <p className="text-lg font-bold font-sinhala text-forest">
                    ආයුබෝවන්!
                  </p>

                  <p className="max-w-sm mx-auto text-sm text-forest-muted">
                    Ask me about rice diseases,
                    pests, symptoms, prevention,
                    or chemical treatments — by
                    typing or tapping the mic.
                    Try one of these to get a
                    full report:
                  </p>

                </div>

                <TopicChips
                  topics={topics}
                  onSelect={(
                    topic
                  ) => {
                    void handleSend(
                      topic
                    )
                  }}
                  disabled={
                    sending
                  }
                />

              </div>

            ) : (

              <>

                {session.messages.map(
                  (message) => {
                    const language =
                      normalizeSpeechLanguage(
                        message.language
                      )

                    return (
                      <ChatBubble
                        key={
                          message.id
                        }
                        message={
                          message
                        }
                        onAskFollowUp={(
                          question
                        ) => {
                          void handleSend(
                            question
                          )
                        }}
                        ttsSupported={
                          tts.supported
                        }
                        speaking={
                          tts.speakingId ===
                          message.id
                        }
                        onToggleSpeak={() => {
                          if (
                            tts.speakingId ===
                            message.id
                          ) {
                            tts.stop()
                          } else {
                            speakMessage(
                              message.id,
                              stripLiteMarkdown(
                                message.content
                              ),
                              language
                            )
                          }
                        }}
                      />
                    )
                  }
                )}

                {sending && (
                  <TypingIndicator />
                )}

              </>
            )}

          </div>

          {/* Composer */}

          <div className="mt-3">

            <ChatComposer
              value={input}
              onChange={
                setInput
              }
              onSend={() => {
                void handleSend()
              }}
              disabled={
                sending
              }
              micSupported={
                recognition.supported
              }
              listening={
                recognition.listening
              }
              interimText={
                recognition.interimTranscript
              }
              onMicToggle={
                handleMicToggle
              }
              micLang={
                micLang
              }
              onToggleMicLang={
                handleToggleMicLang
              }
            />

          </div>
        </>

      ) : (

        /* ==========================================
           HISTORY
           ========================================== */

        <div className="flex-1 space-y-3 overflow-y-auto">

          {archivedChats.length ===
          0 ? (

            <EmptyState
              icon={Clock}
              title="No past conversations yet"
              description="Your previous treatment conversations will appear here."
            />

          ) : (

            archivedChats.map(
              (entry) => (
                <Card
                  key={
                    entry.sessionId
                  }
                  hoverable
                  className="cursor-pointer"
                >

                  <div className="flex items-center justify-between gap-3">

                    {/* Conversation preview */}

                    <div
                      className="flex-1 min-w-0"
                      onClick={() =>
                        setSelectedChat(
                          entry
                        )
                      }
                    >

                      <p className="font-medium truncate text-forest">
                        {chatPreview(
                          entry.messages
                        )}
                      </p>

                      <p className="mt-1 text-xs text-forest-muted">
                        {formatDate(
                          entry.archivedAt
                        )}
                      </p>

                    </div>

                    {/* Message count */}

                    <Badge
                      tone="gray"
                      className="shrink-0"
                    >
                      {
                        entry
                          .messages
                          .length
                      }{' '}
                      msgs
                    </Badge>

                    {/* Continue */}

                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() =>
                        handleContinueChat(
                          entry
                        )
                      }
                    >
                      <Play className="h-3.5 w-3.5" />

                      Continue
                    </Button>

                  </div>

                </Card>
              )
            )

          )}

        </div>
      )}

      {/* ============================================
          NEW CHAT CONFIRMATION
          ============================================ */}

      <ConfirmDialog
        isOpen={
          confirmReset
        }
        title="Start a new chat?"
        message="Your current conversation will be saved in History and a fresh treatment conversation will be started."
        confirmLabel="Start new chat"
        danger
        loading={
          resetting
        }
        onConfirm={() => {
          void handleConfirmReset()
        }}
        onCancel={() =>
          setConfirmReset(
            false
          )
        }
      />

      {/* ============================================
          HISTORY PREVIEW
          ============================================ */}

      <Modal
        isOpen={Boolean(
          selectedChat
        )}
        onClose={() =>
          setSelectedChat(
            null
          )
        }
        title="Treatment Advisor Conversation"
        size="lg"
      >

        <div className="space-y-4">

          {selectedChat?.messages.map(
            (message) => (
              <ChatBubble
                key={
                  message.id
                }
                message={
                  message
                }
              />
            )
          )}

        </div>

        {/* Continue button */}

        {selectedChat && (
          <div className="flex justify-end pt-5 mt-5 border-t border-beige">

            <Button
              variant="primary"
              onClick={() =>
                handleContinueChat(
                  selectedChat
                )
              }
            >
              <Play className="w-4 h-4" />

              Continue this conversation
            </Button>

          </div>
        )}

      </Modal>

    </div>
  )
}