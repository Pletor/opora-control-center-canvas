import { describe, expect, it } from "vitest";
import { cardBlocks, cardView, footCounts, matchesTagFilter, nodeTags } from "./card-model";
import { emptyBranch, emptyNodeWorkflow, type Block } from "@/shared/desktop-state/logic/types";
import type { CanvasNode } from "@/shared/types/logic/types";

const node: CanvasNode = { id: "login", parentId: null, kind: "node", name: "Přihlášení", purpose: "Ověří identitu.", x: 0, y: 0 };

function block(id: string, tags: string[], status: Block["state"]["status"] = "open"): Block {
  return { id, number: id, title: id, text: "", tags, todos: [], images: [], parentBlockId: "",
    state: { status, condition: "", onMet: emptyBranch(), onUnmet: emptyBranch() } };
}

describe("card-model", () => {
  it("blocked and unmet blocks stay unfinished and expose the request", () => {
    const blocked = block("1", [], "blocked");
    blocked.state.note = "Doplň adresu projektu";
    const workflow = { ...emptyNodeWorkflow(), blocks: [blocked, block("2", [], "unmet"), block("3", [], "met")] };
    const view = cardView(node, workflow, 0);
    expect(view.openBlocks).toBe(2);
    expect(view.waitingOnHuman).toEqual([{ blockId: "1", ask: "Doplň adresu projektu" }]);
  });
  it("sjednotí štítky bloků v pořadí prvního výskytu bez duplicit", () => {
    const workflow = { ...emptyNodeWorkflow(), blocks: [block("1", ["auth", "ui"]), block("2", ["ui", "kritické"])] };
    expect(nodeTags(workflow)).toEqual(["auth", "ui", "kritické"]);
  });

  it("do paty dá nejvýš tři štítky a zbytek spočítá", () => {
    const workflow = { ...emptyNodeWorkflow(), blocks: [block("1", ["a", "b", "c", "d", "e"])] };
    const view = cardView(node, workflow, 2);
    expect(view.tags).toEqual(["a", "b", "c"]);
    expect(view.hiddenTags).toBe(2);
  });

  it("počty v patě vynechají nuly a skloňují", () => {
    const workflow = { ...emptyNodeWorkflow(), blocks: [block("1", [], "open"), block("2", [], "met")],
      actions: [{ id: "a", pipelineId: "p", label: "x", params: {} }] };
    expect(footCounts(cardView(node, workflow, 0))).toEqual([
      { value: 1, label: "otevřený blok" },
      { value: 1, label: "akce" },
    ]);
    expect(footCounts(cardView({ ...node, kind: "sector" }, emptyNodeWorkflow(), 7))).toEqual([{ value: 7, label: "uzlů" }]);
  });

  it("do karty jdou jen kořenové bloky v pořadí čísel, s názvem, stavem a porty", () => {
    const child = { ...block("1.1", [], "met"), parentBlockId: "1" };
    const rows = cardBlocks({ blocks: [block("2", [], "blocked"), block("10", []), child, block("1", [], "met")] });
    expect(rows.map((r) => r.number)).toEqual(["1", "2", "10"]);
    expect(rows[0]).toEqual({ id: "1", number: "1", title: "1", status: "met", text: "", ports: [] });
    expect(cardView(node, emptyNodeWorkflow(), 0).rows).toEqual([]);
  });

  it("port bloku dojde na kartu jako tlačítko; starší blok bez portů má prázdnou řadu", () => {
    const withPort = { ...block("1", []), ports: [{ id: "p1", label: "Schváleno" }] };
    expect(cardBlocks({ blocks: [withPort] })[0].ports).toEqual([{ id: "p1", label: "Schváleno" }]);
    expect(cardBlocks({ blocks: [block("1", [])] })[0].ports).toEqual([]);
  });

  it("blok nese svůj text z uzlu do řádku karty", () => {
    const withText = { ...block("1", []), text: "Popis úkolu a jak má vypadat." };
    expect(cardBlocks({ blocks: [withText] })[0].text).toBe("Popis úkolu a jak má vypadat.");
    expect(cardBlocks({ blocks: [block("1", [])] })[0].text).toBe("");
  });

  it("potvrzené done kartu uzavře; návrh agenta ji jen označí", () => {
    const open = cardView(node, emptyNodeWorkflow(), 0);
    expect([open.closed, open.doneProposed]).toEqual([false, false]);
    const proposed = cardView(node, { ...emptyNodeWorkflow(), done: { confirmed: false, at: "t", by: "agent", note: "" } }, 0);
    expect([proposed.closed, proposed.doneProposed]).toEqual([false, true]);
    const closed = cardView(node, { ...emptyNodeWorkflow(), done: { confirmed: true, at: "t", by: "human", note: "" } }, 0);
    expect([closed.closed, closed.doneProposed]).toEqual([true, false]);
  });

  it("filtr štítků zvýrazní jen uzly s daným štítkem a bez filtru všechny", () => {
    const workflow = { ...emptyNodeWorkflow(), blocks: [block("1", ["auth"])] };
    expect(matchesTagFilter(workflow, "auth")).toBe(true);
    expect(matchesTagFilter(workflow, "ui")).toBe(false);
    expect(matchesTagFilter(emptyNodeWorkflow(), "")).toBe(true);
  });
});

describe("card-model: vrstva a stav karty", () => {
  it("uzel bez karty nemá štítky, starší graf se nemění", () => {
    const view = cardView(node, emptyNodeWorkflow(), 0);
    expect(view.cardLayer).toBeNull();
    expect(view.cardStatus).toBeNull();
  });

  it("vrstva jen z karty (ne z předpony), stav done z uzavření", () => {
    const workflow = { ...emptyNodeWorkflow(), done: { confirmed: true, at: "", by: "human" as const, note: "" } };
    expect(cardView({ ...node, name: "[task] Login" }, emptyNodeWorkflow(), 0).cardLayer).toBeNull();
    const view = cardView({ ...node, card: { layer: "database", status: "ready" } }, workflow, 0);
    expect(view.cardLayer).toBe("database");
    expect(view.cardStatus).toBe("done");
  });

  it("sektor vrstvu ani stav nenese", () => {
    const view = cardView({ ...node, kind: "sector", name: "[task] S", card: { layer: "backend", status: "ready" } }, emptyNodeWorkflow(), 0);
    expect(view.cardLayer).toBeNull();
    expect(view.cardStatus).toBeNull();
  });
});
