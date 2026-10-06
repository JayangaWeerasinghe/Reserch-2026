/**
 * LLM client — the OpenAI SDK pointed at OpenRouter, exactly like the
 * notebook's `llm_client = OpenAI(base_url="https://openrouter.ai/api/v1", ...)`.
 */
const OpenAI = require("openai");
const config = require("../config");

if (!config.openrouterApiKey) {
  // eslint-disable-next-line no-console
  console.warn(
    "[llmClient] OPENROUTER_API_KEY is not set — chat completions will fail until it is configured in .env"
  );
}

const llmClient = new OpenAI({
  baseURL: config.openrouterBaseUrl,
  apiKey: config.openrouterApiKey || "missing-api-key",
});

module.exports = llmClient;
