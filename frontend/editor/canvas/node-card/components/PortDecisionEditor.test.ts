import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import PortDecisionEditor from "./PortDecisionEditor";
import { addBlock, addBlockPort, decideBlockPort } from "@/editor/node-detail/tree/logic/tree-model";
import { emptyDesktopState, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";

it("changes or clears a decision without losing the port identity", () => {
  let state = addBlock("n")(emptyDesktopState());
  const block = nodeWorkflowOf(state, "n").blocks[0];
  state = addBlockPort("n", block.id, "Option")(state);
  const original = nodeWorkflowOf(state, "n").blocks[0].ports![0];
  state = decideBlockPort("n", block.id, original.id, "chosen", "Fast")(state);
  expect(nodeWorkflowOf(state, "n").blocks[0].ports![0]).toEqual({ ...original, status: "chosen", reason: "Fast" });
  state = decideBlockPort("n", block.id, original.id, "", "")(state);
  expect(nodeWorkflowOf(state, "n").blocks[0].ports![0]).toEqual(original);
});

it("renders decision and reason controls, preserving read-only state", () => {
  const html = renderToStaticMarkup(createElement(PortDecisionEditor, {
    blockId: "b", port: { id: "p", label: "Option", status: "rejected", reason: "Too slow" }, disabled: true, onSave: () => {},
  }));
  expect(html).toContain("Too slow");
  expect(html).toContain('value="rejected" selected=""');
  expect(html).toContain('disabled=""');
});
