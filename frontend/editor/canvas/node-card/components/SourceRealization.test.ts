import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import SourceRealization from "./SourceRealization";

it("shows missing output, commit and a safe PR link", () => {
  const html = renderToStaticMarkup(createElement(SourceRealization, { nodeId: "n", disabled: false, mergePassed: true, save: async () => {},
    value: { commit: "abc1234", prUrl: "https://git.example/pr/1", verifiedAt: "2026-10-07T12:00:00Z" },
    status: { status: "missing", path: "result.py", origin: "existing" } }));
  expect(html).toContain("Cesta chybí"); expect(html).toContain("abc1234"); expect(html).toContain('href="https://git.example/pr/1"');
});

it("requires merge evidence and never equates unavailable inspection to present", () => {
  const html = renderToStaticMarkup(createElement(SourceRealization, { nodeId: "n", disabled: true, mergePassed: false, save: async () => {} }));
  expect(html).toContain("Cesta neověřena"); expect(html).toContain("Nejprve doložte merge"); expect(html).toContain("disabled");
});
