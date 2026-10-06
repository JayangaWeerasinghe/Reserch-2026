/**
 * Chemical/pesticide extraction — after the main answer is generated, ask
 * the LLM to pull out a structured list of chemicals/dosages/coverage
 * from it, then render a bilingual "Chemical Application Summary" block.
 * Ported from the notebook's extract_chemicals / format_chemical_block.
 */
const config = require("../config");
const llmClient = require("../rag/llmClient");

const CHEMICAL_EXTRACTION_SYSTEM = `You extract chemical/pesticide/fungicide recommendations from the given text.
The text may be in English or Sinhala, but chemical/product names inside it are always kept in English.
Return ONLY valid JSON, no markdown fences, no commentary.
Schema:
{
  "chemicals": [
    {
      "name": "chemical or product name (always in English, never translated)",
      "dose_per_liter_water": "amount (g or ml) to mix per 1L water; if not explicit in text, give a reasonable standard estimate and prefix with 'Approx.'; if truly unknown say 'Not specified'",
      "coverage_per_liter_mixture_acres": "how much land 1L of the prepared mixture covers, in acres (estimate similarly if not explicit)",
      "coverage_per_liter_mixture_hectares": "same coverage in hectares"
    }
  ]
}
If no chemicals/pesticides/fungicides are mentioned, return {"chemicals": []}.
`;

/** @returns {Promise<Array<object>>} extracted chemicals, or [] on any failure */
async function extractChemicals(answerText) {
  try {
    const resp = await llmClient.chat.completions.create({
      model: config.llmModel,
      messages: [
        { role: "system", content: CHEMICAL_EXTRACTION_SYSTEM },
        { role: "user", content: answerText },
      ],
      temperature: 0,
      max_tokens: 600,
    });
    const raw = (resp.choices[0]?.message?.content || "")
      .trim()
      .replace(/```json/g, "")
      .replace(/```/g, "")
      .trim();
    const parsed = JSON.parse(raw);
    return parsed.chemicals || [];
  } catch (err) {
    return [];
  }
}

const CHEM_BLOCK_LABELS = {
  en: {
    header: "**🧪 Chemical Application Summary**",
    dosage: "Dosage",
    perWater: "per 1L water",
    coverage: "Coverage per 1L mixture",
    acres: "acres",
    hectares: "hectares",
    notSpecified: "Not specified",
    unknown: "Unknown",
  },
  si: {
    header: "**🧪 රසායනික භාවිත සාරාංශය**",
    dosage: "මාත්‍රාව",
    perWater: "ජලය ලීටර් 1කට",
    coverage: "මිශ්‍රණය ලීටර් 1කින් ආවරණය කළ හැකි ප්‍රදේශය",
    acres: "අක්කර",
    hectares: "හෙක්ටයාර",
    notSpecified: "සඳහන් නොවේ",
    unknown: "නොදන්නා",
  },
};

/** @param {Array<object>} chemicals @param {"en"|"si"} lang */
function formatChemicalBlock(chemicals, lang = "en") {
  if (!chemicals || !chemicals.length) return "";
  const L = CHEM_BLOCK_LABELS[lang] || CHEM_BLOCK_LABELS.en;
  const lines = [`\n\n---\n${L.header}`];
  for (const c of chemicals) {
    const name = c.name || L.unknown; // chemical names stay in English regardless of lang
    const dose = c.dose_per_liter_water || L.notSpecified;
    const acres = c.coverage_per_liter_mixture_acres || L.notSpecified;
    const hectares = c.coverage_per_liter_mixture_hectares || L.notSpecified;
    lines.push(
      `- **${name}**\n` +
        `  - ${L.dosage}: ${dose} ${L.perWater}\n` +
        `  - ${L.coverage}: ${acres} ${L.acres} / ${hectares} ${L.hectares}`
    );
  }
  return lines.join("\n");
}

module.exports = { extractChemicals, formatChemicalBlock, CHEM_BLOCK_LABELS };
