import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import AssignmentWarning from "./AssignmentWarning";

it("offers comparison on the canvas for a captured handoff", () => {
  const html = renderToStaticMarkup(createElement(AssignmentWarning, {
    project: "p", workspace: "w", nodeId: "n", resultId: "snapshot", source: "handoff",
  }));
  expect(html).toContain("Zadání se změnilo");
  expect(html).toContain("porovnat");
  expect(html).toContain("#fef3c7");
});
