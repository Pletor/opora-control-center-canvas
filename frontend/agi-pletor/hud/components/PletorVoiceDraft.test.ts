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
    expect(html).toContain("Až dokončíš celou myšlenku");
    expect(html).toContain("Pauza nic neodesílá");
  });
  it.each([4000, 8000, 12000])("states the actual selected timeout %s", endpointMs => {
    const html = renderToStaticMarkup(createElement(PletorVoiceDraft, { listening: true, draft: "text", manual: false, endpointMs, onFinish() {} }));
    expect(html).toContain(`po ${endpointMs / 1000} sekundách ticha`);
    expect(html).not.toContain("Pauza nic neodesílá");
  });
  it("does not offer an empty send or a send after listening ended", () => {
    expect(renderToStaticMarkup(createElement(PletorVoiceDraft, { listening: true, draft: " ", manual: false, onFinish: () => {} }))).not.toContain("<button");
    expect(renderToStaticMarkup(createElement(PletorVoiceDraft, { listening: false, draft: "stopped", manual: true, onFinish: () => {} }))).toBe("");
  });
});
