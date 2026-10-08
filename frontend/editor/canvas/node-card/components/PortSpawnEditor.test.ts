import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import PortSpawnEditor from "./PortSpawnEditor";
import { addBlock, addBlockPort, setPortSpawn } from "@/editor/node-detail/tree/logic/tree-model";
import { emptyDesktopState, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";

it("configures and removes a template without changing port identity", () => {
  let state = addBlock("n")(emptyDesktopState());
  const block = nodeWorkflowOf(state, "n").blocks[0];
  state = addBlockPort("n", block.id, "Next")(state);
  const port = nodeWorkflowOf(state, "n").blocks[0].ports![0];
  state = setPortSpawn("n", block.id, port.id, { kind: "spawn", template: { name: "Review" } })(state);
  expect(nodeWorkflowOf(state, "n").blocks[0].ports![0].onMet?.template.name).toBe("Review");
  state = setPortSpawn("n", block.id, port.id, undefined)(state);
  expect(nodeWorkflowOf(state, "n").blocks[0].ports![0]).toEqual(port);
});

it("shows the configured successor and read-only controls", () => {
  const html = renderToStaticMarkup(createElement(PortSpawnEditor, {
    port: { id: "p", label: "Next", onMet: { kind: "spawn", template: { name: "Review", spec: { goal: "Inspect" } } } },
    blockId: "b", disabled: true, onSave: () => {},
  }));
  expect(html).toContain("Navazující karta je nastavená");
  expect(html).toContain("⤳+");
  expect(html).toContain("Review");
  expect(html).toContain("Inspect");
  expect(html).toContain('disabled=""');
});
