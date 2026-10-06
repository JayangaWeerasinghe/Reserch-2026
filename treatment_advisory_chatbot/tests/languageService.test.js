const { detectLanguage, isGreetingOrSmalltalk, greetingResponse } = require("../services/languageService");

test("detects Sinhala text", () => {
  expect(detectLanguage("කොහොමද")).toBe("si");
});

test("detects English text", () => {
  expect(detectLanguage("hello there")).toBe("en");
});

test("recognizes common English greetings and small talk", () => {
  expect(isGreetingOrSmalltalk("Hi!")).toBe(true);
  expect(isGreetingOrSmalltalk("thanks")).toBe(true);
  expect(isGreetingOrSmalltalk("Good morning")).toBe(true);
});

test("does not treat disease questions as greetings", () => {
  expect(isGreetingOrSmalltalk("what causes brown spot?")).toBe(false);
});

test("greetingResponse replies in English for an English greeting", () => {
  expect(greetingResponse("hi")).toMatch(/Rice Leaf Disease/);
});

test("greetingResponse replies in Sinhala for a Sinhala greeting", () => {
  expect(greetingResponse("ආයුබෝවන්")).toMatch(/ආයුබෝවන්/);
});
