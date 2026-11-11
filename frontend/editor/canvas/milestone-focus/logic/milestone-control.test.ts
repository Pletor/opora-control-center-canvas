import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import MilestoneFocusControl from "../components/MilestoneFocusControl";

it("labels legacy 100 percent closure as distinct from unproven integration verification", () => {
  const milestone = { id: "m", title: "Login", area: "Entry", areaId: "entry", cards: ["ui", "api"], closure: 100 };
  const html = renderToStaticMarkup(createElement(MilestoneFocusControl, { choices: [milestone], selected: "m", milestone,
    error: null, loading: false, select: () => {} }));
  expect(html).toContain("Uzavření karet: 100 %");
  expect(html).toContain("Integrační ověření nedoloženo");
  expect(html).toContain("Všechny prvky");
  expect(html).toContain("Login");
});

it("shows reported integration evidence with exact source pins", () => {
  const milestone = { id: "m", title: "Login", area: "Entry", areaId: "entry", cards: ["ui", "api"], closure: 100,
    verification: { verified: true, independent: false, source: "agent-reported execution receipt", acceptedRevision: "revision", headSha: "commit" } };
  const html = renderToStaticMarkup(createElement(MilestoneFocusControl, { choices: [milestone], selected: "m", milestone,
    error: null, loading: false, select: () => {} }));
  expect(html).toContain("Integrační scénář doložen Kanceláří");
  expect(html).toContain("Nejde o nezávislé spuštění");
  expect(html).toContain("revision");
});
