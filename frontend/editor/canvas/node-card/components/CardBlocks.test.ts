import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardBlocks from "./CardBlocks";
it("popup edituje porty bez React Flow contextu a bez duplicitních handles", () => {
  const html = renderToStaticMarkup(createElement(CardBlocks, { id: "n", disabled: false, showHandles: false,
    rows: [{ id: "b", number: "1", title: "Blok", text: "Popis", status: "open", ports: [{id: "p", label: "Výstup"}] }],
    handlers: { add() {}, move() {}, remove() {}, rename() {}, text() {}, addPort() {}, renamePort() {}, removePort() {}, decidePort() {}, configureSpawn() {} },
  }));
  expect(html).toContain("Výstup"); expect(html).toContain("textarea");
  expect(html).toContain('aria-label="Rozhodnutí portu"');
  expect(html).toContain('aria-label="Navazující karta"');
  expect(html).not.toContain("react-flow__handle"); expect(html).toContain("+ port");
});
