import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardDnaOverview from "./CardDnaOverview";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
it("nabízí hint a cílovou záložku všech chybějících a běžících kontrol", () => {
  const data = { view: { name: "Karta", purpose: "Cíl karty", waitingOnHuman: [], tags: [], rows: [] }, blocks: { disabled: false },
    lease: { owner: "Writer", expiresAt: 9999999999, serverOffset: 0, active: true }, releaseLease: async () => {},
    checklist: [{key: "checks", state: "no", label: "Kontroly", hint: "Nastav test"}, {key: "source", state: "run", label: "Kód", hint: "Ověř commit"}, {key: "goal", state: "yes", label: "Cíl", hint: "Už hotovo"}], onTag() {} } as unknown as NodeCardData;
  const html = renderToStaticMarkup(createElement(CardDnaOverview, { nodeId: "n", data, state: {nodes:{}} as DesktopState, onTab() {} }));
  expect(html).toContain("Cíl karty"); expect(html).toContain("Nastav test"); expect(html).toContain("Ověř commit");
  expect(html).toContain('data-target-tab="evidence"'); expect(html).toContain('data-target-tab="code"');
  expect(html).not.toContain("Už hotovo");
  expect(html).toContain("Writer"); expect(html).toContain("Uvolnit převzetí karty agentem");
});
