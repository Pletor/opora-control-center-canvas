import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import NodeSpecHistory from "./NodeSpecHistory";

it("renders the initial loading state with a cancellation control", () => {
  const html = renderToStaticMarkup(createElement(NodeSpecHistory, { project: "p", workspace: "w", nodeId: "n1" }));
  expect(html).toContain("Načítám historii revizí");
  expect(html).toContain("Zrušit");
});
