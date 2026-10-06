/**
 * Query embedding — mirrors the notebook's:
 *   embedder = SentenceTransformer("BAAI/bge-large-en-v1.5")
 *   def embed_query(q): return embedder.encode([q], normalize_embeddings=True)...
 *
 * We use @xenova/transformers (ONNX runtime, pure JS/WASM) so this runs
 * inside plain Node without a Python sidecar. The default model name in
 * config points at the Xenova-converted port of the same BGE model used
 * to build the Pinecone index, so embedding dimensions line up (1024-dim).
 *
 * NOTE: Ingestion of the knowledge base PDFs into Pinecone is done offline
 * by the research notebook (see rice-disease-advisor-final.ipynb, cell 2).
 * This service only ever embeds *queries* for retrieval, it never re-ingests.
 */
const config = require("../config");

let extractorPromise = null;

/** Lazily load (and cache) the feature-extraction pipeline. */
async function getExtractor() {
  if (!extractorPromise) {
    extractorPromise = (async () => {
      // Dynamic import: @xenova/transformers ships as ESM; import() works
      // fine from a CommonJS module in Node 20.
      const { pipeline, env } = await import("@xenova/transformers");
      env.cacheDir = process.env.TRANSFORMERS_CACHE_DIR || "./.cache/models";
      // eslint-disable-next-line no-console
      console.log(`[embedder] Loading embedding model "${config.embedModelName}" (first call only)...`);
      return pipeline("feature-extraction", config.embedModelName);
    })();
  }
  return extractorPromise;
}

/** Embed a single query string, mean-pooled and L2-normalized. */
async function embedQuery(text) {
  const extractor = await getExtractor();
  const output = await extractor(text, { pooling: "mean", normalize: true });
  return Array.from(output.data);
}

/**
 * Force the model to load right now instead of on the first real user
 * request. Call this once at server startup so the (potentially slow,
 * network-dependent) download/cold-start cost is paid before traffic
 * arrives, not inside a request that the gateway is timing out on.
 */
async function warmUp() {
  const start = Date.now();
  await getExtractor();
  // Run one throwaway inference too — first inference call also incurs
  // WASM/graph compilation cost separate from just loading the weights.
  await embedQuery("warmup");
  console.log(`[embedder] Warm-up complete in ${((Date.now() - start) / 1000).toFixed(1)}s`);
}

module.exports = { embedQuery, warmUp };