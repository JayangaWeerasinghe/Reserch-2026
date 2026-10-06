/**
 * Central configuration for the C4 Treatment Advisory Chatbot.
 * Mirrors the settings used in the `rice-disease-advisor-final` research
 * notebook (OpenRouter LLM + Pinecone vector store + BGE embeddings),
 * but reads everything from environment variables so it can run as a
 * long-lived Node service instead of a notebook.
 */
require("dotenv").config();

module.exports = {
  port: process.env.PORT || 8004,
  allowedOrigins: (process.env.ALLOWED_ORIGINS || "*").split(","),

  // LLM (OpenRouter — OpenAI-compatible API)
  openrouterApiKey: process.env.OPENROUTER_API_KEY,
  openrouterBaseUrl: process.env.OPENROUTER_BASE_URL || "https://openrouter.ai/api/v1",
  llmModel: process.env.LLM_MODEL || "openai/gpt-4o-mini",

  // Pinecone vector database (populated offline by the ingestion notebook)
  pineconeApiKey: process.env.PINECONE_API_KEY,
  pineconeHost: process.env.PINECONE_HOST,
  pineconeIndexName: process.env.PINECONE_INDEX_NAME || "rice-disease-advisor",

  // Embedding model — must match the dimension used when the Pinecone index
  // was created (1024-dim, BAAI/bge-large-en-v1.5). We use the Xenova ONNX
  // port so it can run inside plain Node without a Python sidecar.
  embedModelName: process.env.EMBED_MODEL_NAME || "Xenova/bge-large-en-v1.5",

  // Retrieval tuning
  retrievalTopK: parseInt(process.env.RETRIEVAL_TOP_K || "6", 10),
  retrievalTopKBareTopic: parseInt(process.env.RETRIEVAL_TOP_K_BARE_TOPIC || "8", 10),
};
