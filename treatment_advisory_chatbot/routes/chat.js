/** Chat routes: POST /chat, GET /chat/topics, DELETE /chat/session/:sessionId */
const express = require("express");
const router = express.Router();
const { handleChatMessage } = require("../services/chatService");
const sessionStore = require("../services/sessionStore");
const { ALL_TOPICS_LIST } = require("../data/diseasesPests");

router.post("/chat", async (req, res) => {
  const { message, session_id } = req.body;

  if (!message || !session_id) {
    return res.status(400).json({ detail: "message and session_id are required" });
  }

  try {
    const result = await handleChatMessage(message, session_id);
    res.json(result);
  } catch (err) {
    console.error("[chat] Error:", err.message);
    res.status(500).json({ detail: err.message });
  }
});

/** List the rice diseases/pests this chatbot is scoped to — useful for the frontend UI. */
router.get("/chat/topics", (req, res) => {
  res.json({ topics: ALL_TOPICS_LIST });
});

/** Clear a session's conversation history (e.g. when the user starts a new chat). */
router.delete("/chat/session/:sessionId", (req, res) => {
  sessionStore.clearSession(req.params.sessionId);
  res.json({ detail: "session cleared" });
});

module.exports = router;
