import { describe, expect, it } from "vitest";
import {
  addBlock, addBlockPort, addTag, addTodo, branchLabel, branchTargets, moveBlock, ordered, removeBlock,
  removeBlockPort, renameBlockPort, renumber, setBranch, setDone, toggleTodo,
} from "./tree-model";
import { blockPorts, emptyDesktopState, MAX_BLOCK_PORTS, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";

function tree() {
  let state = addBlock("n")(emptyDesktopState());
  state = addBlock("n")(state);
  const [first] = nodeWorkflowOf(state, "n").blocks;
  state = addBlock("n", first.id)(state);
  state = addBlock("n", first.id)(state);
  return state;
}

describe("tree-model", () => {
  it("čísluje bloky podle rodiče a pořadí: 1, 1.1, 1.2, 2", () => {
    const blocks = nodeWorkflowOf(tree(), "n").blocks;
    expect(ordered(blocks).map(({ block, depth }) => [block.number, depth])).toEqual([["1", 0], ["1.1", 1], ["1.2", 1], ["2", 0]]);
  });

  it("přesun mezi sourozenci přečísluje a nepřeskočí hranici rodiče", () => {
    let state = tree();
    const child = ordered(nodeWorkflowOf(state, "n").blocks)[2].block; // 1.2
    state = moveBlock("n", child.id, -1)(state);
    expect(nodeWorkflowOf(state, "n").blocks.find((b) => b.id === child.id)?.number).toBe("1.1");
    const same = moveBlock("n", child.id, -1)(state);
    expect(nodeWorkflowOf(same, "n").blocks.find((b) => b.id === child.id)?.number).toBe("1.1");
  });

  it("odebrání bloku vezme podstrom a vyprázdní větve, které na něj mířily", () => {
    let state = tree();
    const [root, child, , other] = ordered(nodeWorkflowOf(state, "n").blocks).map((x) => x.block);
    state = setBranch("n", other.id, "onMet", { kind: "block", targetId: child.id, note: "" })(state);
    state = removeBlock("n", root.id)(state);
    const blocks = nodeWorkflowOf(state, "n").blocks;
    expect(blocks.map((b) => b.number)).toEqual(["1"]);
    expect(blocks[0].state.onMet).toEqual({ kind: "none", targetId: "", note: "" });
  });

  it("TODO a štítky mají ID a nedublují se", () => {
    let state = tree();
    const root = ordered(nodeWorkflowOf(state, "n").blocks)[0].block;
    state = addTodo("n", root.id, "Napsat test", "builder")(state);
    const todo = nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!.todos[0];
    expect(todo.id).toBeTruthy();
    state = toggleTodo("n", root.id, todo.id)(state);
    expect(nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!.todos[0].done).toBe(true);
    state = addTag("n", root.id, "auth")(state);
    state = addTag("n", root.id, "auth")(state);
    expect(nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!.tags).toEqual(["auth"]);
  });

  it("osiřelý blok se přichytí ke kořeni místo zmizení", () => {
    const blocks = renumber([{ ...ordered(nodeWorkflowOf(tree(), "n").blocks)[1].block, parentBlockId: "ghost" }]);
    expect(blocks[0]).toMatchObject({ number: "1", parentBlockId: "" });
  });

  it("porty bloku: přidání dá jméno a unikátní id, přejmenování ořízne na 80 znaků, odebrání zmizí", () => {
    let state = tree();
    const root = ordered(nodeWorkflowOf(state, "n").blocks)[0].block;
    state = addBlockPort("n", root.id)(state);
    state = addBlockPort("n", root.id, "Schváleno")(state);
    let ports = blockPorts(nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!);
    expect(ports.map((p) => p.label)).toEqual(["Port 1", "Schváleno"]);
    expect(new Set(ports.map((p) => p.id)).size).toBe(2);
    state = renameBlockPort("n", root.id, ports[1].id, "x".repeat(200))(state);
    ports = blockPorts(nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!);
    expect(ports[1].label).toHaveLength(80);
    state = removeBlockPort("n", root.id, ports[0].id)(state);
    expect(blockPorts(nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!)).toHaveLength(1);
  });

  it("nad osm portů blok nepřidá a starší blok bez portů se čte jako prázdný", () => {
    let state = tree();
    const root = ordered(nodeWorkflowOf(state, "n").blocks)[0].block;
    expect(blockPorts(root)).toEqual([]);
    for (let i = 0; i < MAX_BLOCK_PORTS + 3; i += 1) state = addBlockPort("n", root.id)(state);
    expect(blockPorts(nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!)).toHaveLength(MAX_BLOCK_PORTS);
  });

  it("uzavření karty razítkuje čas, drží poznámku a dá se znovu otevřít", () => {
    let state = setDone("n", { confirmed: true, by: "human", note: "Hotovo, testy prošly." })(emptyDesktopState());
    let done = nodeWorkflowOf(state, "n").done;
    expect(done.confirmed).toBe(true);
    expect(done.by).toBe("human");
    expect(done.at).not.toBe("");
    state = setDone("n", { confirmed: false })(state);
    done = nodeWorkflowOf(state, "n").done;
    expect(done.confirmed).toBe(false);
    expect(done.note).toBe("Hotovo, testy prošly.");
    expect(nodeWorkflowOf(emptyDesktopState(), "n").done).toEqual({ confirmed: false, at: "", by: "human", note: "" });
  });

  it("nabídka cílů větve vynechá blok sám a popíše cíl", () => {
    const state = tree();
    const node = nodeWorkflowOf(state, "n");
    const root = ordered(node.blocks)[0].block;
    const targets = branchTargets(node, root.id, [{ id: "menu", name: "Menu" }]);
    expect(targets.some((t) => t.id === root.id)).toBe(false);
    expect(targets.find((t) => t.kind === "node")).toEqual({ kind: "node", id: "menu", label: "Menu" });
    expect(branchLabel({ kind: "node", targetId: "menu", note: "" }, targets)).toBe("uzel: Menu");
    expect(branchLabel({ kind: "none", targetId: "", note: "" }, targets)).toBe("nic dalšího");
  });
});
