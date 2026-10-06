const { keywordScopeHit, isBareTopicName, ALL_TOPICS_LIST } = require("../data/diseasesPests");

test("keywordScopeHit finds a match for a synonym", () => {
  expect(keywordScopeHit("I think this is bacterial leaf blight")).toBe("Rice Bacterial Leaf Blight");
});

test("keywordScopeHit matches a Sinhala keyword", () => {
  expect(keywordScopeHit("මට දුඹුරු මකුණා පිළිබඳ දැනගැනීමට අවශ්‍යයි")).toBe("Brown Planthopper");
});

test("keywordScopeHit returns null when nothing matches", () => {
  expect(keywordScopeHit("what time does the market open")).toBeNull();
});

test("isBareTopicName matches the canonical name and synonyms", () => {
  expect(isBareTopicName("Rice Leaf Blast")).toBe("Rice Leaf Blast");
  expect(isBareTopicName("bph")).toBe("Brown Planthopper");
  expect(isBareTopicName("  hispa  ")).toBe("Rice Hispa");
});

test("isBareTopicName returns null when the input has extra words", () => {
  expect(isBareTopicName("brown spot causes")).toBeNull();
});

test("ALL_TOPICS_LIST exposes every canonical disease/pest name", () => {
  expect(ALL_TOPICS_LIST).toHaveLength(8);
  expect(ALL_TOPICS_LIST).toContain("Rice Stem Borer");
});
