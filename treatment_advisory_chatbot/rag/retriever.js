/**
 * Retrieval module — semantic search over the Pinecone index that the
 * ingestion notebook populated from the rice disease/pest PDF knowledge
 * base. Mirrors the notebook's `retrieve_context(query, top_k)`.
 */
const { Pinecone } = require("@pinecone-database/pinecone");
const config = require("../config");
const { embedQuery } = require("./embedder");

let pineconeIndex = null;

function getIndex() {
  if (!pineconeIndex) {
    if (!config.pineconeApiKey) {
      throw new Error("PINECONE_API_KEY is not configured");
    }
    const pc = new Pinecone({ apiKey: config.pineconeApiKey });
    pineconeIndex = config.pineconeHost
      ? pc.index(config.pineconeIndexName, config.pineconeHost)
      : pc.index(config.pineconeIndexName);
  }
  return pineconeIndex;
}

/**
 * Retrieve the top-k most relevant knowledge base chunks for `query`.
 * Returns [{ text, source, score }, ...].
 */
async function retrieveContext(query, topK = config.retrievalTopK) {
  const vector = await embedQuery(query);
  const index = getIndex();
  const result = await index.query({ vector, topK, includeMetadata: true });

  return (result.matches || []).map((match) => ({
    text: match.metadata?.text || "",
    source: match.metadata?.source || "",
    score: match.score,
  }));
}

module.exports = { retrieveContext };
