/**
 * In-memory session history — mirrors the notebook's
 * `SESSIONS = defaultdict(list)` (full history replayed every turn).
 *
 * NOTE: this resets whenever the process restarts. If persistent,
 * multi-instance chat history is needed later, swap this module for a
 * Mongo-backed store (the `mongoose` dependency this service used to ship
 * with) without touching chatService.js.
 */
const sessions = new Map();

function getHistory(sessionId) {
  if (!sessions.has(sessionId)) {
    sessions.set(sessionId, []);
  }
  return sessions.get(sessionId);
}

function appendTurn(sessionId, userInput, assistantReply) {
  const history = getHistory(sessionId);
  history.push({ role: "user", content: userInput });
  history.push({ role: "assistant", content: assistantReply });
}

function clearSession(sessionId) {
  sessions.delete(sessionId);
}

module.exports = { getHistory, appendTurn, clearSession };
