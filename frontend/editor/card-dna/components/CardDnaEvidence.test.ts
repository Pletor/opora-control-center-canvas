import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardDnaEvidence from "./CardDnaEvidence";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { CanvasNode } from "@/shared/types/logic/types";
it("zobrazuje běhy stránkovaně jako tabulku, editor důkazů až na vyžádání", () => {
  const proof = { status: "passed", note: "Doloženo", url: "https://example.org/proof" };
  const data = { view: { checks: [] }, blocks: { disabled: false }, evidence: { tests: proof, review: proof, merge: proof,
    checksRun: Array.from({length: 200}, (_,i) => ({ checkId: `check-${i}`, command: `run-${i}`, exitCode: 0, logUrl: "", at: "2026-10-08" })) }, saveEvidence: async () => true } as unknown as NodeCardData;
  const html = renderToStaticMarkup(createElement(CardDnaEvidence, { node: { id: "n" } as CanvasNode, data }));
  expect(html).toContain("Upravit důkazy"); expect(html).toContain("run-0"); expect(html).not.toContain("run-199");
  expect(html).toContain("Další"); expect(html).toContain("<table"); expect(html).not.toMatch(/<(input|textarea|select)\b/);
});
