import { create } from 'zustand'
import type { ChemicalEntry } from '@/lib/chatApi'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  language?: 'en' | 'si'
  inScope?: boolean
  chemicals?: ChemicalEntry[]
  followUpQuestion?: string | null
}

export interface ArchivedChat {
  sessionId: string
  messages: ChatMessage[]
  archivedAt: string
}

interface StoredChat {
  sessionId: string
  messages: ChatMessage[]
}

const STORAGE_KEY = 'paddyguard_chat_sessions'
const HISTORY_STORAGE_KEY = 'paddyguard_chat_history'

const MAX_MESSAGES = 200
const MAX_HISTORY = 50

function newSessionId(): string {
  return crypto.randomUUID()
}

/*
 * --------------------------------------------------
 * LOAD CURRENT SESSIONS
 * --------------------------------------------------
 */

function loadAll(): Record<string, StoredChat> {
  if (typeof window === 'undefined') {
    return {}
  }

  const raw = localStorage.getItem(
    STORAGE_KEY
  )

  if (!raw) {
    return {}
  }

  try {
    return JSON.parse(
      raw
    ) as Record<string, StoredChat>
  } catch {
    return {}
  }
}

/*
 * --------------------------------------------------
 * LOAD HISTORY
 * --------------------------------------------------
 */

function loadHistory(): Record<
  string,
  ArchivedChat[]
> {
  if (typeof window === 'undefined') {
    return {}
  }

  const raw = localStorage.getItem(
    HISTORY_STORAGE_KEY
  )

  if (!raw) {
    return {}
  }

  try {
    return JSON.parse(
      raw
    ) as Record<string, ArchivedChat[]>
  } catch {
    return {}
  }
}

/*
 * --------------------------------------------------
 * PERSIST CURRENT SESSIONS
 * --------------------------------------------------
 */

function persistAll(
  sessions: Record<string, StoredChat>
): void {
  if (typeof window === 'undefined') {
    return
  }

  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(sessions)
  )
}

/*
 * --------------------------------------------------
 * PERSIST HISTORY
 * --------------------------------------------------
 */

function persistHistory(
  history: Record<string, ArchivedChat[]>
): void {
  if (typeof window === 'undefined') {
    return
  }

  localStorage.setItem(
    HISTORY_STORAGE_KEY,
    JSON.stringify(history)
  )
}

/*
 * --------------------------------------------------
 * STORE INTERFACE
 * --------------------------------------------------
 */

interface ChatState {
  sessions: Record<string, StoredChat>

  history: Record<
    string,
    ArchivedChat[]
  >

  /*
   * Creates a session only when one doesn't exist.
   */
  ensureSession: (
    userId: string
  ) => void

  /*
   * Always archives the existing session if it
   * contains messages, then creates a new session.
   */
  startNewSession: (
    userId: string
  ) => string

  /*
   * Adds a message to the current session.
   */
  addMessage: (
    userId: string,
    message: Omit<
      ChatMessage,
      'id' | 'timestamp'
    > & {
      id?: string
    }
  ) => ChatMessage

  /*
   * Continue an archived conversation.
   *
   * The archived conversation becomes the current
   * session and keeps the SAME sessionId.
   *
   * NOTE: this no longer removes the entry from
   * History. The chat stays visible there while
   * it's active. If the user later starts a new
   * chat, startNewSession() will re-archive this
   * same sessionId with its latest messages,
   * replacing the stale copy rather than losing it.
   */
  continueSession: (
    userId: string,
    archived: ArchivedChat
  ) => string

  /*
   * Archives current chat and starts new chat.
   */
  resetSession: (
    userId: string
  ) => string
}

/*
 * --------------------------------------------------
 * ZUSTAND STORE
 * --------------------------------------------------
 */

export const useChatStore =
  create<ChatState>((set, get) => ({
    sessions: loadAll(),

    history: loadHistory(),

    /*
     * ------------------------------------------------
     * ENSURE SESSION
     * ------------------------------------------------
     */

    ensureSession: (userId) => {
      const existing =
        get().sessions[userId]

      if (existing) {
        return
      }

      const fresh: StoredChat = {
        sessionId: newSessionId(),
        messages: [],
      }

      const sessions = {
        ...get().sessions,
        [userId]: fresh,
      }

      persistAll(sessions)

      set({
        sessions,
      })
    },

    /*
     * ------------------------------------------------
     * START COMPLETELY NEW SESSION
     *
     * Used when TreatmentChat initially opens.
     *
     * Existing messages are automatically archived.
     *
     * FIX: previously this only archived a session if
     * no History entry for that sessionId existed yet
     * ("alreadyArchived" check). Combined with
     * continueSession() removing the entry on
     * Continue, that meant: continue a chat, add new
     * messages, open a new chat -> the entry either
     * never came back, or came back stale. Now we
     * always replace any existing entry for this
     * sessionId with the latest messages, the same
     * way resetSession() already does.
     * ------------------------------------------------
     */

    startNewSession: (userId) => {
      const current =
        get().sessions[userId]

      let history =
        get().history

      /*
       * Archive the existing chat if it contains
       * messages.
       */
      if (
        current &&
        current.messages.length > 0
      ) {
        const archived: ArchivedChat = {
          sessionId:
            current.sessionId,
          messages:
            current.messages,
          archivedAt:
            new Date().toISOString(),
        }

        const existingHistory =
          history[userId] || []

        /*
         * Replace any existing entry for this
         * session (e.g. one that was continued and
         * picked up new messages) instead of
         * skipping it — keeps History up to date
         * and avoids duplicates.
         */
        const filteredHistory =
          existingHistory.filter(
            (entry) =>
              entry.sessionId !==
              archived.sessionId
          )

        history = {
          ...history,
          [userId]: [
            archived,
            ...filteredHistory,
          ].slice(
            0,
            MAX_HISTORY
          ),
        }

        persistHistory(
          history
        )
      }

      /*
       * Create a completely fresh session.
       */
      const fresh: StoredChat = {
        sessionId:
          newSessionId(),
        messages: [],
      }

      const sessions = {
        ...get().sessions,
        [userId]: fresh,
      }

      persistAll(sessions)

      set({
        sessions,
        history,
      })

      return fresh.sessionId
    },

    /*
     * ------------------------------------------------
     * ADD MESSAGE
     * ------------------------------------------------
     */

    addMessage: (
      userId,
      message
    ) => {
      let current =
        get().sessions[userId]

      /*
       * Safety fallback.
       */
      if (!current) {
        current = {
          sessionId:
            newSessionId(),
          messages: [],
        }
      }

      const full: ChatMessage = {
        ...message,

        id:
          message.id ||
          crypto.randomUUID(),

        timestamp:
          new Date().toISOString(),
      }

      const messages = [
        ...current.messages,
        full,
      ].slice(
        -MAX_MESSAGES
      )

      const updated: StoredChat = {
        ...current,
        messages,
      }

      const sessions = {
        ...get().sessions,
        [userId]: updated,
      }

      persistAll(sessions)

      set({
        sessions,
      })

      return full
    },

    /*
     * ------------------------------------------------
     * CONTINUE ARCHIVED CHAT
     *
     * This is the important part.
     *
     * We keep the original sessionId so the backend
     * can continue the same conversation.
     *
     * FIX: this used to filter the entry out of
     * History immediately, which made it look like
     * the conversation was "deleted" the moment you
     * pressed Continue. History is just a list of
     * saved conversations — switching the active
     * session shouldn't remove the record of it. We
     * now leave History untouched here; it gets kept
     * in sync (replaced, not duplicated) the next
     * time startNewSession() or resetSession() runs.
     * ------------------------------------------------
     */

    continueSession: (
      userId,
      archived
    ) => {
      const continued: StoredChat = {
        sessionId:
          archived.sessionId,

        messages:
          archived.messages,
      }

      const sessions = {
        ...get().sessions,
        [userId]: continued,
      }

      persistAll(sessions)

      set({
        sessions,
      })

      return continued.sessionId
    },

    /*
     * ------------------------------------------------
     * RESET SESSION
     *
     * Used by the "New chat" button.
     * ------------------------------------------------
     */

    resetSession: (userId) => {
      const current =
        get().sessions[userId]

      let history =
        get().history

      /*
       * Archive current conversation.
       */
      if (
        current &&
        current.messages.length > 0
      ) {
        const archived: ArchivedChat = {
          sessionId:
            current.sessionId,

          messages:
            current.messages,

          archivedAt:
            new Date().toISOString(),
        }

        const existingHistory =
          history[userId] || []

        /*
         * Remove an older copy of the same
         * session first.
         */
        const filteredHistory =
          existingHistory.filter(
            (entry) =>
              entry.sessionId !==
              current.sessionId
          )

        history = {
          ...history,

          [userId]: [
            archived,
            ...filteredHistory,
          ].slice(
            0,
            MAX_HISTORY
          ),
        }

        persistHistory(
          history
        )
      }

      /*
       * Create fresh session.
       */
      const fresh: StoredChat = {
        sessionId:
          newSessionId(),

        messages: [],
      }

      const sessions = {
        ...get().sessions,
        [userId]: fresh,
      }

      persistAll(sessions)

      set({
        sessions,
        history,
      })

      return fresh.sessionId
    },
  }))