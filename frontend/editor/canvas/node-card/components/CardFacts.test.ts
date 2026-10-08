import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardFacts, { resolveFacts } from "./CardFacts";

it("resolves shared current values and explicitly reports deleted facts", () => {
  const refs = ["pilot", "missing"];
  const before = resolveFacts(refs, [{ id: "pilot", key: "Pilot", value: "old" }]);
  const after = resolveFacts(refs, [{ id: "pilot", key: "Pilot", value: "new" }]);
  expect(before[0].fact?.value).toBe("old"); expect(after[0].fact?.value).toBe("new");
  const html = renderToStaticMarkup(createElement(CardFacts, { facts: after }));
  expect(html).toContain("new"); expect(html).toContain("Chybějící fakt missing"); expect(html).toContain("Fakta projektu");
});
