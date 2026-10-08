import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardDnaCompactIndicators from "./CardDnaCompactIndicators";
import { cardView } from "@/editor/canvas/node-card/logic/card-model";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { NodeWorkflowFull } from "@/shared/desktop-state/logic/types";

it("ukazuje skutečné etapy pipeline, nikoli počet běhů kontrol", () => {
  const view = { checks: [] } as unknown as ReturnType<typeof cardView>;
  const html = renderToStaticMarkup(createElement(CardDnaCompactIndicators, {
    view, assignmentChanged: true, pipeline: { finished: 2, total: 4, failed: 1 },
    commit: "abcdef123456", tokens: 50,
  }));
  expect(html).toContain('title="Pipeline: dokončené etapy / celkem"');
  expect(html).toContain("2/4");
  expect(html).toContain("1 selhání");
  expect(html).toContain("abcdef1");
  expect(html).toContain("zadání se změnilo");
});
