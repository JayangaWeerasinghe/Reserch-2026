/**
 * Orchestrates the full RAG pipeline for a chat turn — greeting/small-talk
 * short-circuit, scope gating, retrieval, generation, chemical-summary
 * extraction, and a follow-up question suggestion. This is a direct port
 * of the `chat(session_id, user_input)` function from cell 5/6 of
 * rice-disease-advisor-final.ipynb, adapted to Node + Express.
 */
const config = require("../config");
const llmClient = require("../rag/llmClient");
const { retrieveContext } = require("../rag/retriever");
const { ALL_TOPICS_LIST, keywordScopeHit, isBareTopicName } = require("../data/diseasesPests");
const { isInScope } = require("./scopeService");
const { detectLanguage, isGreetingOrSmalltalk, greetingResponse } = require("./languageService");
const { extractChemicals, formatChemicalBlock } = require("./chemicalService");
const sessionStore = require("./sessionStore");

const BASE_SYSTEM_PROMPT = `You are "Rice Leaf Disease and Pest Advisor", an expert assistant strictly specialized in:
${ALL_TOPICS_LIST.join(", ")}

IMPORTANT: Scope filtering has ALREADY been done before this message reached you. Every message you
receive here is guaranteed to be in-scope. Do NOT re-evaluate whether the topic is allowed, do NOT apologize,
and do NOT say things like "I can only provide information on..." or "I'm sorry, but...". Just answer directly.

LANGUAGE RULE: The user may ask in English or Sinhala. Detect the language of the user's CURRENT message and
respond in that SAME language. However, NEVER translate chemical names, product/brand names, or scientific
names (e.g. pathogen names like "Xanthomonas oryzae", pest species names, chemical compounds like
"Mancozeb", "Chlorpyrifos" etc.) — always keep those exact terms in English even inside a Sinhala response.

Rules:
1. Answer using the provided knowledge base context and conversation history.
2. Prioritize the provided knowledge base context. Use your own knowledge only to fill gaps, without contradicting the context.
3. Match the user's requested format (bullet points, table, paragraph, etc.); default to clear structured text.
4. If the user's message is ONLY a disease/pest name (no other text), give a full detailed report: overview, causal organism, symptoms, favorable conditions, prevention/cultural control, chemical treatment, management tips.
5. Resolve follow-up questions (e.g. "what about treatments for that?" / Sinhala equivalents) using the conversation history to identify which disease/pest is being referred to.
6. Never include any scope disclaimer, apology, or meta-commentary about what topics you can/cannot cover — just answer.
`;

const PRONOUN_PATTERN = /\b(that|this|it|those|these)\b|(එය|ඒක|මේක|මෙය)/i;

/**
 * If the message looks like a pronoun-based follow-up, pull the most
 * recently discussed topic from history so retrieval targets the right
 * disease/pest.
 */
function resolveQueryForRetrieval(userInput, history) {
  if (!PRONOUN_PATTERN.test(userInput)) return userInput;
  for (let i = history.length - 1; i >= 0; i--) {
    const hit = keywordScopeHit(history[i].content);
    if (hit) return `${userInput} (${hit})`;
  }
  return userInput;
}

function buildContextBlock(chunks) {
  if (!chunks || !chunks.length) return "No relevant knowledge base context found.";
  return chunks.map((c) => `[Source: ${c.source}]\n${c.text}`).join("\n\n");
}

const SCOPE_PREAMBLE_PATTERNS = [
  /^i'?m sorry,?\s*but\s*i\s*can\s*only[^.]*\.\s*/i,
  /^unfortunately,\s*i\s*(can\s*not|cannot|can't)[^.]*\.\s*/i,
  /^i\s*can\s*only\s*provide\s*information\s*on[^.]*\.\s*(since you mentioned[^.]*\.\s*)?/i,
];

/**
 * Safety net: if the LLM still slips in an apologetic scope preamble
 * despite instructions, strip leading sentences that look like scope
 * disclaimers.
 */
function stripScopePreamble(answer) {
  let cleaned = answer;
  for (const pattern of SCOPE_PREAMBLE_PATTERNS) {
    cleaned = cleaned.replace(pattern, "");
  }
  return cleaned.trim();
}

/** Generate one short, relevant follow-up question in the same language as the response. */
async function generateFollowupQuestion(userInput, answerText, lang) {
  const langName = lang === "si" ? "Sinhala" : "English";
  const system =
    "Based on the user's question and the assistant's answer below (about rice diseases/pests), " +
    "suggest exactly ONE short, natural follow-up question the user might want to ask next. " +
    `Write it in ${langName}. Keep any chemical/scientific names in English even in a Sinhala question. ` +
    "Return ONLY the question text, nothing else — no numbering, no quotes, no preamble.";
  try {
    const resp = await llmClient.chat.completions.create({
      model: config.llmModel,
      messages: [
        { role: "system", content: system },
        { role: "user", content: `User question: ${userInput}\n\nAssistant answer: ${answerText.slice(0, 1500)}` },
      ],
      temperature: 0.5,
      max_tokens: 60,
    });
    return (resp.choices[0]?.message?.content || "").trim().replace(/^"|"$/g, "");
  } catch (err) {
    console.error("[chatService] follow-up generation failed:", err.message);
    return null;
  }
}

function formatFollowupBlock(question, lang) {
  if (!question) return "";
  // Normalize: strip trailing punctuation, lowercase the first letter (English
  // only) so it reads naturally inside the wrapping sentence.
  let q = question.trim().replace(/\?+$/, "").replace(/।+$/, "").trim();

  let wrapped;
  if (lang === "si") {
    wrapped = `ඔබට දැනගැනීමට කැමතිද, ${q}?`;
  } else {
    if (q) q = q[0].toLowerCase() + q.slice(1);
    wrapped = `Do you want to know ${q}?`;
  }
  return `\n\n💬 ${wrapped}`;
}

function declineMessage(lang) {
  if (lang === "si") {
    return (
      "සමාවන්න, මට ගොයම් රෝග සහ පළිබෝධ පිළිබඳ ප්‍රශ්නවලට පමණක් (ප්‍රතිකාර ඇතුළුව) උදව් කළ හැක: " +
      `${ALL_TOPICS_LIST.join(", ")}. කරුණාකර මේ මාතෘකා වලට අදාළ ප්‍රශ්නයක් අසන්න.`
    );
  }
  return (
    "I'm sorry, but I can only help with questions about these rice diseases and pests " +
    `(including their treatments): ${ALL_TOPICS_LIST.join(", ")}. ` +
    "Could you please ask something related to these topics?"
  );
}

/**
 * @param {string} userInput
 * @param {string} sessionId
 * @returns {Promise<object>} chat result payload
 */
async function handleChatMessage(userInput, sessionId) {
  const history = sessionStore.getHistory(sessionId);
  const lang = detectLanguage(userInput);

  // 1. Greeting / small talk — answered directly, no LLM call, no follow-up.
  if (isGreetingOrSmalltalk(userInput)) {
    const reply = greetingResponse(userInput);
    sessionStore.appendTurn(sessionId, userInput, reply);
    return { session_id: sessionId, reply, language: lang, in_scope: true, chemicals: [], follow_up_question: null };
  }

  // 2. Scope gate — decline anything unrelated to the supported diseases/pests.
  const inScope = await isInScope(userInput, history);
  if (!inScope) {
    const decline = declineMessage(lang);
    sessionStore.appendTurn(sessionId, userInput, decline);
    return {
      session_id: sessionId,
      reply: decline,
      language: lang,
      in_scope: false,
      chemicals: [],
      follow_up_question: null,
    };
  }

  // 3. Retrieval — bare topic names get a wider top_k for a full report.
  const bareTopic = isBareTopicName(userInput);
  const retrievalQuery = bareTopic || resolveQueryForRetrieval(userInput, history);
  const topK = bareTopic ? config.retrievalTopKBareTopic : config.retrievalTopK;
  const chunks = await retrieveContext(retrievalQuery, topK);
  const contextBlock = buildContextBlock(chunks);

  const instruction = bareTopic
    ? `The user asked about: ${bareTopic}. Provide a COMPLETE, DETAILED report covering overview, ` +
      "causal organism/pest identity, symptoms, favorable conditions, cultural/biological prevention, " +
      "and full chemical treatment recommendations."
    : "Answer the user's question using the context and conversation history. If the question refers " +
      "back to a previously discussed disease/pest, resolve the reference from the conversation history " +
      "before answering. Remember: this message is already confirmed in-scope, so answer directly " +
      "without any disclaimer, and respond in the same language as the user's current message.";

  // NOTE: full history is replayed every call for "unlimited" memory, same
  // as the notebook. For very long sessions this can approach the model's
  // context window — consider summarizing older turns if that becomes an issue.
  const messages = [
    { role: "system", content: BASE_SYSTEM_PROMPT },
    ...history,
    {
      role: "user",
      content: `Knowledge base context:\n${contextBlock}\n\n${instruction}\n\nUser message: ${userInput}`,
    },
  ];

  // 4. Generation
  const completion = await llmClient.chat.completions.create({
    model: config.llmModel,
    messages,
    temperature: 0.3,
    max_tokens: 1500,
  });
  const rawAnswer = completion.choices[0]?.message?.content?.trim() || "";
  const answer = stripScopePreamble(rawAnswer);

  // 5. Chemical summary extraction
  const chemicals = await extractChemicals(answer);
  const chemBlock = formatChemicalBlock(chemicals, lang);

  // 6. Follow-up question suggestion
  const followupQ = await generateFollowupQuestion(userInput, answer, lang);
  const followupBlock = formatFollowupBlock(followupQ, lang);

  const finalAnswer = answer + chemBlock + followupBlock;

  sessionStore.appendTurn(sessionId, userInput, finalAnswer);

  return {
    session_id: sessionId,
    reply: finalAnswer,
    language: lang,
    in_scope: true,
    chemicals,
    follow_up_question: followupQ,
    sources: chunks.map((c) => c.source),
  };
}

module.exports = { handleChatMessage, BASE_SYSTEM_PROMPT };
