/**
 * Scope gating — decides whether a user message is about one of the
 * supported rice diseases/pests before any RAG generation happens.
 * Ported from the notebook's `is_in_scope(user_input, history)`.
 */
const config = require("../config");
const llmClient = require("../rag/llmClient");
const { ALL_TOPICS_LIST, keywordScopeHit } = require("../data/diseasesPests");

/**
 * @param {string} userInput
 * @param {{role: string, content: string}[]} history
 * @returns {Promise<boolean>}
 */
async function isInScope(userInput, history = []) {
  // Fast path: direct keyword/synonym match needs no LLM call.
  if (keywordScopeHit(userInput)) return true;

  // Give the classifier a little recent context so follow-ups like
  // "what are the treatments for that?" resolve against the prior topic
  // instead of being judged in isolation.
  let contextSnippet = "";
  if (history.length) {
    const recent = history.slice(-4);
    contextSnippet = recent.map((m) => `${m.role}: ${String(m.content).slice(0, 300)}`).join("\n");
  }

  const system =
    "You are a strict topic classifier. The user's message may be in English or Sinhala. " +
    "Reply with exactly YES or NO, nothing else. " +
    "Reply YES only if the CURRENT MESSAGE, considering the recent conversation context provided, " +
    `is about one or more of these rice diseases/pests, or their symptoms/causes/prevention/treatment: ` +
    `${ALL_TOPICS_LIST.join(", ")}. This includes follow-up questions that use pronouns like 'that', 'it', ` +
    "'this disease' (or Sinhala equivalents like 'එය', 'මේක', 'ඒක') referring to a topic already discussed " +
    "in the recent context. Anything unrelated to these topics is NO, regardless of language.";

  const userContent = contextSnippet
    ? `Recent conversation context:\n${contextSnippet}\n\nCurrent message: ${userInput}`
    : userInput;

  const resp = await llmClient.chat.completions.create({
    model: config.llmModel,
    messages: [
      { role: "system", content: system },
      { role: "user", content: userContent },
    ],
    temperature: 0,
    max_tokens: 5,
  });

  return (resp.choices[0]?.message?.content || "").trim().toUpperCase().startsWith("YES");
}

module.exports = { isInScope };
