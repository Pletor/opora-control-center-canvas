import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import PletorVoiceDraft from "./PletorVoiceDraft";

describe("pending thought", () => {
  it("shows the complete draft and explicit manual completion without a deadline", () => {
    const draft = "První věta. ".repeat(100) + "Poslední věta.";
    const html = renderToStaticMarkup(createElement(PletorVoiceDraft, { listening: true, draft, manual: true, onFinish: () => {} }));
    expect(html).toContain(draft);
    expect(html).toContain("Domluvil jsem</button>");
    expect(html).toContain("Odešlu až po stisknutí");
    expect(html).toContain("Máš čas dokončit myšlenku.");
  });
  it("does not offer an empty send or a send after listening ended", () => {
    expect(renderToStaticMarkup(createElement(PletorVoiceDraft, { listening: true, draft: " ", manual: false, onFinish: () => {} }))).not.toContain("<button");
    expect(renderToStaticMarkup(createElement(PletorVoiceDraft, { listening: false, draft: "stopped", manual: true, onFinish: () => {} }))).toBe("");
  });
});
