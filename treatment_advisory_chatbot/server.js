/**
 * PaddyGuard AI — C4 Treatment Advisory Chatbot
 * Owner: Keshan Fernando (IT22303820)
 * Handles: RAG-based treatment recommendations for the supported rice
 * diseases/pests, backed by a Pinecone vector store + OpenRouter LLM
 * (see rag/retriever.js, rag/llmClient.js, services/chatService.js).
 */
require("dotenv").config();
const express = require("express");
const cors = require("cors");

const chatRoutes = require("./routes/chat");
const config = require("./config");
const { warmUp } = require("./rag/embedder");

const app = express();
const PORT = config.port;

app.use(cors({ origin: config.allowedOrigins }));
app.use(express.json());

app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "treatment_advisory_chatbot", component: "C4" });
});

app.get("/", (req, res) => {
  res.json({ message: "PaddyGuard AI Treatment Advisory Chatbot is running" });
});

app.use("/", chatRoutes);

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`[treatment_advisory_chatbot] C4 service started on port ${PORT}`);
    // Load the embedding model now, at boot, instead of on the first real
    // chat request. Without this, the first user message pays the full
    // model download/cold-start cost inline and can exceed the gateway's
    // request timeout (seen as a 504 "Treatment chatbot service timed out").
    warmUp().catch((err) => {
      console.error("[embedder] Warm-up failed — first real request will retry loading the model:", err.message);
    });
  });
}

module.exports = app;