import { describe, expect, it } from "vitest";
import { addBlockOfKind, closeLibrary, contextChecks, contextScore, initialLibrary, linkedBlockPorts, openLibrary, showSection } from "./library-model";
import { emptyBranch, emptyDesktopState, emptyNodeWorkflow, nodeWorkflowOf, type Block } from "@/shared/desktop-state/logic/types";
import type { GraphEdge } from "@/shared/types/logic/types";

describe("library-model: lišta a panel", () => {
  it("začíná zavřený; výběr karty ho otevře, záložka přepne sekci a panel zůstává otevřený", () => {
    const start = initialLibrary();
    expect(start.open).toBe(false);
    const opened = openLibrary(start);
    expect(opened).toEqual({ open: true, section: "blocks" });
    expect(showSection(opened, "actions")).toEqual({ open: true, section: "actions" });
    expect(showSection(closeLibrary(opened), "materials")).toEqual({ open: true, section: "materials" });
  });

  it("zavření zachová poslední sekci a stejný stav vrací stejný objekt", () => {
    const closed = closeLibrary(showSection(initialLibrary(), "context"));
    expect(openLibrary(closed)).toEqual({ open: true, section: "context" });
    expect(closeLibrary(closed)).toBe(closed);
  });
});

describe("library-model: vložení bloku podle druhu", () => {
  it("přidá očíslovaný blok s předvyplněním podle druhu", () => {
    let state = emptyDesktopState();
    state = addBlockOfKind("n1", "text")(state);
    state = addBlockOfKind("n1", "checklist")(state);
    state = addBlockOfKind("n1", "condition")(state);
    const blocks = nodeWorkflowOf(state, "n1").blocks;
    expect(blocks.map((b) => b.number)).toEqual(["1", "2", "3"]);
    expect(blocks[0].title).toBe("Nový text");
    expect(blocks[1].todos).toHaveLength(1);
    expect(blocks[2].state.condition).not.toBe("");
    expect(blocks[2].state.status).toBe("open");
  });
});

describe("library-model: kontrola kontextu", () => {
  const block = (extra: Partial<Block>): Block => ({
    id: "b", number: "1", title: "b", text: "", tags: [], todos: [], images: [], parentBlockId: "",
    state: { status: "open", condition: "", onMet: emptyBranch(), onUnmet: emptyBranch() }, ...extra,
  });

  it("prázdný uzel nemá nic splněné a každá položka nese nápovědu", () => {
    const checks = contextChecks({ id: "n1", name: "x", purpose: "" }, emptyNodeWorkflow());
    expect(checks.every((c) => !c.ok && c.hint.length > 0)).toBe(true);
    expect(contextScore(checks)).toEqual({ done: 0, total: 7 });
  });

  it("cíl, blok s textem, pravidlo, podmínka, podklad, akce a navázaný port zaškrtnou svou položku", () => {
    const workflow = {
      ...emptyNodeWorkflow(),
      blocks: [block({
        text: "udělej", ports: [{ id: "p1", label: "Hotovo" }],
        state: { status: "open", condition: "test prošel", onMet: emptyBranch(), onUnmet: emptyBranch() },
      })],
      rules: [{ id: "r", text: "nesahat na schéma", kind: "must_not" as const }],
      materials: [{ id: "m", kind: "link" as const, path: "https://x", caption: "" }],
      actions: [{ id: "a", pipelineId: "p", label: "p", params: {} }],
    };
    const edges: GraphEdge[] = [{ id: "e1", source: "n1", target: "n2", port: "block", sourceBlockId: "b", sourcePortId: "p1" }];
    const checks = contextChecks({ id: "n1", name: "x", purpose: "Přihlásí uživatele." }, workflow, edges);
    expect(contextScore(checks)).toEqual({ done: 7, total: 7 });
    expect(checks.map((c) => c.id)).toEqual(["goal", "blocks", "rules", "acceptance", "materials", "actions", "ports"]);
  });

  it("port bez vazby, vazba z cizí karty ani vazba na neznámý port kontrolu portů nezaškrtnou", () => {
    const workflow = { ...emptyNodeWorkflow(), blocks: [block({ ports: [{ id: "p1", label: "Hotovo" }] })] };
    const node = { id: "n1", name: "x", purpose: "" };
    expect(linkedBlockPorts(node, workflow, [])).toEqual([]);
    expect(linkedBlockPorts(node, workflow, [{ id: "e", source: "jiny", target: "n2", port: "block", sourceBlockId: "b", sourcePortId: "p1" }])).toEqual([]);
    expect(linkedBlockPorts(node, workflow, [{ id: "e", source: "n1", target: "n2", port: "block", sourceBlockId: "b", sourcePortId: "duch" }])).toEqual([]);
    expect(linkedBlockPorts(node, workflow, [{ id: "e", source: "n1", target: "n2", port: "next" }])).toEqual([]);
    expect(linkedBlockPorts(node, workflow, [{ id: "e", source: "n1", target: "n2", port: "block", sourceBlockId: "b", sourcePortId: "p1" }])).toEqual(["b:p1"]);
  });
});
