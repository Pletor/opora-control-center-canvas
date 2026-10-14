import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardEvidence, { type CompletionEvidence } from "./CardEvidence";

it("never shows missing evidence as passed", () => {
  const html = renderToStaticMarkup(createElement(CardEvidence, {}));
  expect(html).not.toContain("node-card__chip--ok");
  expect(html).toContain("Důkaz nedoložen");
});

it("shows links and commands while distinguishing failed and inapplicable proofs", () => {
  const evidence: CompletionEvidence = {
    tests: { status: "passed", url: "https://ci.example/run", note: "Passed" },
    review: { status: "failed", url: "https://git.example/review", note: "Needs fixes" },
    merge: { status: "not_applicable", url: "", note: "Research" },
    checksRun: [{ checkId: "unit", command: "uv run pytest", exitCode: 0, logUrl: "https://ci.example/log", at: "2026-10-07T12:00:00Z" }],
  };
  const html = renderToStaticMarkup(createElement(CardEvidence, { evidence }));
  expect(html).toContain("node-card__chip--ok");
  expect(html).toContain("node-card__chip--fail");
  expect(html).toContain("Nevztahuje se");
  expect(html).toContain("uv run pytest");
  expect(html).toContain('href="https://ci.example/log"');
});

it("labels evidence as declared, not server-verified, and accepts local test runs", () => {
  const evidence: CompletionEvidence = {
    tests: { status: "passed", url: "", note: "Local run" },
    review: { status: "pending", url: "", note: "" },
    merge: { status: "pending", url: "", note: "" },
    checksRun: [{ checkId: "unit", command: "npm test", exitCode: 0, logUrl: "", at: "2026-10-07T12:00:00Z" }],
  };
  const html = renderToStaticMarkup(createElement(CardEvidence, { evidence }));
  expect(html).toContain("deklarováno");
  expect(html).toContain("neověřeno serverem");
  expect(html).toContain("node-card__chip--ok");
});
