jest.mock("../rag/llmClient", () => ({
  chat: { completions: { create: jest.fn() } },
}));
jest.mock("../rag/retriever", () => ({
  retrieveContext: jest.fn(),
}));

const request = require("supertest");
const app = require("../server");
const llmClient = require("../rag/llmClient");
const { retrieveContext } = require("../rag/retriever");

afterEach(() => jest.clearAllMocks());

describe("GET /health", () => {
  it("returns service status", async () => {
    const res = await request(app).get("/health");
    expect(res.statusCode).toBe(200);
    expect(res.body.service).toBe("treatment_advisory_chatbot");
  });
});

describe("GET /chat/topics", () => {
  it("lists the supported diseases and pests", async () => {
    const res = await request(app).get("/chat/topics");
    expect(res.statusCode).toBe(200);
    expect(res.body.topics).toContain("Rice Leaf Blast");
  });
});

describe("POST /chat", () => {
  it("returns 400 when message is missing", async () => {
    const res = await request(app).post("/chat").send({ session_id: "test" });
    expect(res.statusCode).toBe(400);
  });

  it("returns 400 when session_id is missing", async () => {
    const res = await request(app).post("/chat").send({ message: "hello" });
    expect(res.statusCode).toBe(400);
  });

  it("returns a greeting reply without calling the LLM", async () => {
    const res = await request(app).post("/chat").send({ message: "hello", session_id: "greet-1" });
    expect(res.statusCode).toBe(200);
    expect(res.body.reply).toMatch(/Rice Leaf Disease and Pest Advisor/);
    expect(llmClient.chat.completions.create).not.toHaveBeenCalled();
  });

  it("declines out-of-scope questions via the LLM classifier", async () => {
    llmClient.chat.completions.create.mockResolvedValueOnce({
      choices: [{ message: { content: "NO" } }],
    });
    const res = await request(app)
      .post("/chat")
      .send({ message: "what is the capital of France?", session_id: "scope-1" });
    expect(res.statusCode).toBe(200);
    expect(res.body.in_scope).toBe(false);
    expect(res.body.reply).toMatch(/only help with questions/i);
  });

  it("answers an in-scope question using retrieved context", async () => {
    retrieveContext.mockResolvedValueOnce([
      { text: "Brown spot is caused by a fungus.", source: "kb.pdf", score: 0.9 },
    ]);
    llmClient.chat.completions.create
      .mockResolvedValueOnce({
        choices: [{ message: { content: "Brown spot symptoms include oval lesions with yellow halos." } }],
      }) // main answer
      .mockResolvedValueOnce({ choices: [{ message: { content: '{"chemicals": []}' } }] }) // chemical extraction
      .mockResolvedValueOnce({ choices: [{ message: { content: "how to prevent brown spot" } }] }); // follow-up

    const res = await request(app).post("/chat").send({ message: "brown spot symptoms", session_id: "scope-2" });

    expect(res.statusCode).toBe(200);
    expect(res.body.in_scope).toBe(true);
    expect(res.body.reply).toContain("Brown spot symptoms");
    expect(res.body.reply).toMatch(/Do you want to know/);
    expect(retrieveContext).toHaveBeenCalledWith("brown spot symptoms", 6);
  });
});

describe("DELETE /chat/session/:sessionId", () => {
  it("clears a session's history", async () => {
    const res = await request(app).delete("/chat/session/some-session");
    expect(res.statusCode).toBe(200);
  });
});
