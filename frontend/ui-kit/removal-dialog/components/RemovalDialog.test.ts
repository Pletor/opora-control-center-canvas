import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import RemovalDialog from "./RemovalDialog";

const preview = { project: "p", workspace: "w", kind: "selection" as const, target: "", label: "Výběr", nodeIds: ["a", "b"], nodeCount: 2, edgeCount: 0, digest: "d" };
const render = (confirmedNodeIds?: string[]) => renderToStaticMarkup(createElement(RemovalDialog, {
  preview: { ...preview, confirmedNodeIds }, onClose: () => {}, onConfirm: async () => {} }));

it("warns how many closed cards the removal includes", () => {
  expect(render(["a"])).toContain("z toho uzavřené: <strong data-testid=\"removal-confirmed-count\">1</strong>");
  expect(render([])).not.toContain("z toho uzavřené");
  expect(render()).not.toContain("z toho uzavřené");
});
