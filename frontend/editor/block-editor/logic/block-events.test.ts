import { describe, expect, it } from "vitest";
import { blockEditorEvents, blockEvents } from "./block-events";
import { addBlock } from "@/editor/node-detail/tree/logic/tree-model";
import { blockPorts, emptyDesktopState, nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";

function fixture(): DesktopState {
  let state = addBlock("n")(emptyDesktopState());
  state = addBlock("n")(state);
  return state;
}

/** Falešný `run`: aplikuje mutaci na lokální proměnnou a chová se jako skutečný zápis (vždy uspěje). */
function harness() {
  let state = fixture();
  const root = nodeWorkflowOf(state, "n").blocks[0];
  const run = async (fn: (current: DesktopState) => DesktopState) => {
    state = fn(state);
    return true;
  };
  return {
    get: () => state,
    block: () => nodeWorkflowOf(state, "n").blocks.find((b) => b.id === root.id)!,
    rootId: root.id,
    run,
  };
}

describe("blockEvents", () => {
  it("onTitle a onText uloží pole", () => {
    const h = harness();
    const events = blockEvents("n", h.rootId, h.run);
    events.onTitle("Nový název");
    expect(h.block().title).toBe("Nový název");
    events.onText("Nový text");
    expect(h.block().text).toBe("Nový text");
  });

  it("onStatus a onCondition mění stav bloku, zbytek stavu zůstává", () => {
    const h = harness();
    const events = blockEvents("n", h.rootId, h.run);
    events.onCondition("Testy zelené");
    events.onStatus("met");
    expect(h.block().state).toMatchObject({ status: "met", condition: "Testy zelené" });
  });

  it("onBranch zapíše větev na existující blok", () => {
    const h = harness();
    const second = nodeWorkflowOf(h.get(), "n").blocks[1];
    const events = blockEvents("n", h.rootId, h.run);
    events.onBranch("onMet", { kind: "block", targetId: second.id, note: "pak dál" });
    expect(h.block().state.onMet).toEqual({ kind: "block", targetId: second.id, note: "pak dál" });
  });

  it("onAddChild přidá podblok a po úspěchu zavolá extras.onAddChild", async () => {
    const h = harness();
    let expandedFor: string | null = null;
    const events = blockEvents("n", h.rootId, h.run, { onAddChild: () => { expandedFor = h.rootId; } });
    const before = nodeWorkflowOf(h.get(), "n").blocks.length;
    events.onAddChild();
    await Promise.resolve();
    const after = nodeWorkflowOf(h.get(), "n").blocks;
    expect(after.length).toBe(before + 1);
    expect(after.some((b) => b.parentBlockId === h.rootId)).toBe(true);
    expect(expandedFor).toBe(h.rootId);
  });

  it("onMove a onRemove přesunou a odeberou blok", () => {
    const h = harness();
    const events0 = blockEvents("n", h.rootId, h.run);
    const [, second] = nodeWorkflowOf(h.get(), "n").blocks;
    const eventsSecond = blockEvents("n", second.id, h.run);
    eventsSecond.onMove(-1);
    expect(nodeWorkflowOf(h.get(), "n").blocks.find((b) => b.id === second.id)?.number).toBe("1");
    events0.onRemove();
    expect(nodeWorkflowOf(h.get(), "n").blocks.some((b) => b.id === h.rootId)).toBe(false);
  });

  it("TODO: přidání, přepnutí a odebrání", () => {
    const h = harness();
    const events = blockEvents("n", h.rootId, h.run);
    events.onAddTodo("Napsat test", "builder");
    const todo = h.block().todos[0];
    expect(todo.text).toBe("Napsat test");
    events.onToggleTodo(todo.id);
    expect(h.block().todos[0].done).toBe(true);
    events.onRemoveTodo(todo.id);
    expect(h.block().todos).toHaveLength(0);
  });

  it("štítky: přidání se nedubluje, odebrání zmizí", () => {
    const h = harness();
    const events = blockEvents("n", h.rootId, h.run);
    events.onAddTag("auth");
    events.onAddTag("auth");
    expect(h.block().tags).toEqual(["auth"]);
    events.onRemoveTag("auth");
    expect(h.block().tags).toEqual([]);
  });

  it("obrázky: přidání a odebrání", () => {
    const h = harness();
    const events = blockEvents("n", h.rootId, h.run);
    events.onAddImage("docs/mockups/login.png", "přihlášení");
    const image = h.block().images[0];
    expect(image).toMatchObject({ path: "docs/mockups/login.png", caption: "přihlášení" });
    events.onRemoveImage(image.id);
    expect(h.block().images).toHaveLength(0);
  });

  it("onPickTag se předává beze změny", () => {
    const h = harness();
    const picked: string[] = [];
    const events = blockEvents("n", h.rootId, h.run, { onPickTag: (tag) => picked.push(tag) });
    events.onPickTag?.("auth");
    expect(picked).toEqual(["auth"]);
  });
});

describe("blockEditorEvents", () => {
  it("porty: přidání, přejmenování, odebrání", () => {
    const h = harness();
    const events = blockEditorEvents("n", h.rootId, h.run, { onSelectChild: () => {} });
    events.onAddPort();
    const port = blockPorts(h.block())[0];
    expect(port.label).toBe("Port 1");
    events.onRenamePort(port.id, "Schváleno");
    expect(blockPorts(h.block())[0].label).toBe("Schváleno");
    events.onRemovePort(port.id);
    expect(blockPorts(h.block())).toHaveLength(0);
  });

  it("onSelectChild se předává beze změny a zbytek TreeBlockEvents funguje", () => {
    const h = harness();
    const selected: string[] = [];
    const events = blockEditorEvents("n", h.rootId, h.run, { onSelectChild: (id) => selected.push(id) });
    events.onSelectChild("child-1");
    expect(selected).toEqual(["child-1"]);
    events.onTitle("Přejmenováno z editoru");
    expect(h.block().title).toBe("Přejmenováno z editoru");
  });
});
