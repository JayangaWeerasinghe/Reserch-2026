/**
 * Canonical rice disease/pest taxonomy the chatbot is scoped to, plus the
 * English/Sinhala synonym keywords used for fast, LLM-free scope checks.
 * Ported directly from the `rice-disease-advisor-final` notebook.
 */
const DISEASES_PESTS = {
  "Rice Bacterial Leaf Blight": ["bacterial leaf blight", "blb", "bacterial blight", "බැක්ටීරියා පත්‍ර අංගමාරය"],
  "Rice Leaf Blast": ["leaf blast", "rice blast", "blast", "තලා රෝගය", "බ්ලාස්ට් රෝගය"],
  "Rice Brown Spot": ["brown spot", "දුඹුරු පුල්ලි රෝගය"],
  "Brown Planthopper": ["brown planthopper", "bph", "planthopper", "දුඹුරු මකුණා"],
  "Rice Gall Midge": ["gall midge", "ගොයම් මකුණා"],
  "Rice Leaf Folder": ["leaf folder", "කොළ නවන පණුවා"],
  "Rice Hispa": ["hispa", "හිස්පා පණුවා"],
  "Rice Stem Borer": ["stem borer", "stemborer", "stem-borer", "කඳ කණුවා"],
};

const ALL_TOPICS_LIST = Object.keys(DISEASES_PESTS);

/**
 * Fast, deterministic scope check: does `text` contain any keyword/synonym
 * (or the canonical name itself) for one of the supported diseases/pests?
 * Returns the canonical name on a hit, or null.
 */
function keywordScopeHit(text) {
  const t = String(text || "").toLowerCase();
  for (const [canonical, keywords] of Object.entries(DISEASES_PESTS)) {
    const candidates = [...keywords, canonical].map((k) => k.toLowerCase());
    if (candidates.some((kw) => t.includes(kw))) {
      return canonical;
    }
  }
  return null;
}

/**
 * Returns the canonical disease/pest name if `userInput` is *only* that
 * name (or one of its synonyms) with nothing else — used to trigger the
 * "full detailed report" response mode.
 */
function isBareTopicName(userInput) {
  const t = String(userInput || "").trim().toLowerCase();
  for (const [canonical, keywords] of Object.entries(DISEASES_PESTS)) {
    const candidates = [canonical, ...keywords].map((k) => k.toLowerCase());
    if (candidates.includes(t)) {
      return canonical;
    }
  }
  return null;
}

module.exports = { DISEASES_PESTS, ALL_TOPICS_LIST, keywordScopeHit, isBareTopicName };
