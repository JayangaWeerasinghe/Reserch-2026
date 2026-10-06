/**
 * Bilingual (English / Sinhala) language detection and greeting/small-talk
 * short-circuit, ported from the notebook's detect_language / is_greeting_
 * or_smalltalk / greeting_response.
 */
const GREETING_PATTERNS_EN = [
  /^\s*hi+\s*[!.]*\s*$/i,
  /^\s*hello+\s*[!.]*\s*$/i,
  /^\s*hey+\s*[!.]*\s*$/i,
  /^\s*good\s*(morning|afternoon|evening)\s*[!.]*\s*$/i,
  /^\s*(how are you|what'?s up|sup)\s*[?!.]*\s*$/i,
  /^\s*(thanks|thank you|thx)\s*[!.]*\s*$/i,
  /^\s*(bye|goodbye|see you)\s*[!.]*\s*$/i,
];

// Common Sinhala greeting/small-talk phrases (extend as needed for real usage).
const GREETING_KEYWORDS_SI = [
  "ආයුබෝවන්",
  "හෙලෝ",
  "සුභ උදෑසනක්",
  "සුභ දවසක්",
  "කොහොමද",
  "ස්තුතියි",
  "බොහොම ස්තුතියි",
  "බායි",
  "ගිහින් එන්නම්",
];

/** Sinhala Unicode block: U+0D80–U+0DFF */
function detectLanguage(text) {
  return /[\u0D80-\u0DFF]/.test(String(text || "")) ? "si" : "en";
}

function isGreetingOrSmalltalk(text) {
  const t = String(text || "").trim();
  if (GREETING_PATTERNS_EN.some((p) => p.test(t))) return true;
  if (t.length <= 30 && GREETING_KEYWORDS_SI.some((kw) => t.includes(kw))) return true;
  return false;
}

function greetingResponse(userInput) {
  const lang = detectLanguage(userInput);
  const t = String(userInput || "").trim().toLowerCase();

  if (lang === "si") {
    if (["ස්තුතියි", "බොහොම ස්තුතියි"].some((kw) => userInput.includes(kw))) {
      return "ඔබට සුභ පතමි! රෝග හෝ පළිබෝධ පිළිබඳ ප්‍රශ්න තිබේ නම් අසන්න.";
    }
    if (["බායි", "ගිහින් එන්නම්"].some((kw) => userInput.includes(kw))) {
      return "ආයුබෝවන්! නැවත අවශ්‍ය විටක ගොයම් රෝග හෝ පළිබෝධ පිළිබඳ මගෙන් අසන්න.";
    }
    return (
      "ආයුබෝවන්! 👋 මම ඔබේ ගොයම් රෝග සහ පළිබෝධ උපදේශකයා. පහත ගැන තොරතුරු, රෝග ලක්ෂණ සහ ප්‍රතිකාර ලබා දිය හැක:\n\n" +
      "**රෝග:** Rice Bacterial Leaf Blight, Rice Leaf Blast, Rice Brown Spot\n" +
      "**පළිබෝධ:** Brown Planthopper, Rice Gall Midge, Rice Leaf Folder, Rice Hispa, Rice Stem Borer\n\n" +
      "ඔබට දැනගැනීමට අවශ්‍ය කුමක්ද?"
    );
  }

  if (/^\s*(thanks|thank you|thx)\s*[!.]*\s*$/i.test(t)) {
    return "You're welcome! Let me know if you have any questions about rice diseases or pests.";
  }
  if (/^\s*(bye|goodbye|see you)\s*[!.]*\s*$/i.test(t)) {
    return "Goodbye! Feel free to come back anytime you need help with rice diseases or pests.";
  }
  return (
    "Hello! 👋 I'm your Rice Leaf Disease and Pest Advisor. I can help you with information, " +
    "symptoms, and treatments for:\n\n" +
    "**Diseases:** Rice Bacterial Leaf Blight, Rice Leaf Blast, Rice Brown Spot\n" +
    "**Pests:** Brown Planthopper, Rice Gall Midge, Rice Leaf Folder, Rice Hispa, Rice Stem Borer\n\n" +
    "What would you like to know?"
  );
}

module.exports = { detectLanguage, isGreetingOrSmalltalk, greetingResponse };
