import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardFrontier from "./CardFrontier";

it("names the blocking card and displays a human request", () => {
  const html = renderToStaticMarkup(createElement(CardFrontier, { item: {
    id: "n", name: "Next", status: "waiting", blockedBy: [{ id: "a", name: "Database" }], waitingOnHuman: [{ blockId: "b", ask: "Need URL" }],
  } }));
  expect(html).toContain("Čeká na člověka");
  expect(html).toContain("Database");
  expect(html).toContain("Need URL");
});
