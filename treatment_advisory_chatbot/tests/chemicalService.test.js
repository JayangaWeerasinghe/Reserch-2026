jest.mock("../rag/llmClient", () => ({
  chat: { completions: { create: jest.fn() } },
}));

const llmClient = require("../rag/llmClient");
const { extractChemicals, formatChemicalBlock } = require("../services/chemicalService");

describe("extractChemicals", () => {
  afterEach(() => jest.clearAllMocks());

  it("parses chemicals from a valid JSON LLM response", async () => {
    llmClient.chat.completions.create.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content:
              '{"chemicals": [{"name": "Mancozeb", "dose_per_liter_water": "2.5g", ' +
              '"coverage_per_liter_mixture_acres": "0.1", "coverage_per_liter_mixture_hectares": "0.04"}]}',
          },
        },
      ],
    });
    const chemicals = await extractChemicals("Apply Mancozeb 2.5g per litre of water.");
    expect(chemicals).toHaveLength(1);
    expect(chemicals[0].name).toBe("Mancozeb");
  });

  it("returns an empty array when the LLM call fails", async () => {
    llmClient.chat.completions.create.mockRejectedValueOnce(new Error("network error"));
    const chemicals = await extractChemicals("no chemicals here");
    expect(chemicals).toEqual([]);
  });
});

describe("formatChemicalBlock", () => {
  it("returns an empty string when there are no chemicals", () => {
    expect(formatChemicalBlock([], "en")).toBe("");
  });

  it("formats an English chemical block", () => {
    const block = formatChemicalBlock([{ name: "Tricyclazole", dose_per_liter_water: "0.6g" }], "en");
    expect(block).toContain("Chemical Application Summary");
    expect(block).toContain("Tricyclazole");
  });

  it("formats a Sinhala chemical block", () => {
    const block = formatChemicalBlock([{ name: "Tricyclazole", dose_per_liter_water: "0.6g" }], "si");
    expect(block).toContain("රසායනික භාවිත සාරාංශය");
    expect(block).toContain("Tricyclazole"); // chemical names stay in English
  });
});
