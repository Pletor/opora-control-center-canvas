import { describe, expect, it } from "vitest";
import { emptyDesktopState, nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";
import {
  blockFromItem,
  blockTextFromItem,
  cardFromItem,
  insertBlockFromItem,
  RELATES_BLOCK_TITLE,
  TEMPLATE_BLOCK_TITLE,
  workflowFromItem,
} from "./catalog-insert";
import { itemById, type CatalogItem } from "./library-catalog";

/** Zkušební prvek: základ, ke kterému se v testu dopisuje jen to, co se zkouší. */
const fixture = (patch: Partial<CatalogItem> = {}): CatalogItem => ({
  id: "fixture",
  category: "fe-components",
  label: "Zkušební prvek",
  purpose: "Jen pro test.",
  relates: ["@fe-pure-model", "Data jdou přes rodiče."],
  done: ["Test prochází."],
  invariants: [
    { kind: "must", text: "Musí platit A" },
    { kind: "must_not", text: "Nesmí C" },
  ],
  steps: [
    { title: "Dílek", text: "Jedno pole" },
    { title: "Logika", text: "Čistá funkce" },
  ],
  template: "// logic/form-model.ts\nexport function validate() {}",
  ...patch,
});

const pure = itemById("fe-pure-model")!;

describe("catalog-insert – nová karta", () => {
  it("jméno je popisek a účel je purpose prvku", () => {
    const card = cardFromItem(fixture(), "sektor", 120.4, 40.6);
    expect(card.kind).toBe("node");
    expect(card.parentId).toBe("sektor");
    expect(card.name).toBe("Zkušební prvek");
    expect(card.purpose).toBe("Jen pro test.");
    expect({ x: card.x, y: card.y }).toEqual({ x: 120, y: 41 });
  });

  it("bloky jsou Souvisí s, kroky a Šablona; @id je přeložené na název a účel", () => {
    const workflow = workflowFromItem(fixture());
    expect(workflow.blocks.map((b) => [b.number, b.title])).toEqual([
      ["1", RELATES_BLOCK_TITLE],
      ["2", "Dílek"],
      ["3", "Logika"],
      ["4", TEMPLATE_BLOCK_TITLE],
    ]);
    expect(workflow.blocks[0].text).toBe(`- ${pure.label}: ${pure.purpose}\n- Data jdou přes rodiče.`);
    expect(workflow.blocks[3].text).toBe("// logic/form-model.ts\nexport function validate() {}");
  });

  it("hotovo jde do kritérií a invarianty do pravidel uzlu", () => {
    const workflow = workflowFromItem(fixture());
    expect(workflow.criteria.map((c) => [c.text, c.checked])).toEqual([["Test prochází.", false]]);
    expect(workflow.rules.map((r) => [r.kind, r.text])).toEqual([
      ["must", "Musí platit A"],
      ["must_not", "Nesmí C"],
    ]);
    expect(workflow.phase).toBe("discover");
    expect(workflow.actions).toEqual([]);
  });

  it("prvek bez souvislostí, kroků a šablony nedá prázdné bloky", () => {
    const workflow = workflowFromItem(fixture({ relates: [], steps: undefined, template: undefined }));
    expect(workflow.blocks).toEqual([]);
  });

  it("vydaný prvek „Formulář s validací“ dá kartu se souvislostmi, kroky, kritérii i šablonou", () => {
    const item = itemById("fe-form-validated")!;
    const workflow = workflowFromItem(item);
    expect(workflow.blocks[0].title).toBe(RELATES_BLOCK_TITLE);
    expect(workflow.blocks.length).toBe(1 + (item.steps?.length ?? 0) + 1);
    expect(workflow.criteria.length).toBe(item.done.length);
  });
});

describe("catalog-insert – blok do karty", () => {
  it("text má účel, Souvisí s, Hotovo, Kroky a šablonu v tomto pořadí", () => {
    expect(blockTextFromItem(fixture())).toBe(
      [
        "Jen pro test.",
        `Souvisí s:\n- ${pure.label}: ${pure.purpose}\n- Data jdou přes rodiče.`,
        "Hotovo, když:\n- Test prochází.",
        "Kroky:\n1. Dílek — Jedno pole\n2. Logika — Čistá funkce",
        "// logic/form-model.ts\nexport function validate() {}",
      ].join("\n\n"),
    );
    const block = blockFromItem(fixture({ category: "fe-css" }));
    expect(block.title).toBe("Zkušební prvek");
    expect(block.tags).toEqual(["fe-css"]);
  });

  it("vložení doplní blok na konec, přečísluje a přidá invarianty bez duplicit", () => {
    const start: DesktopState = emptyDesktopState();
    const first = insertBlockFromItem("uzel", fixture({ label: "Mřížka" }))(start);
    const second = insertBlockFromItem("uzel", fixture({ label: "Řádek" }))(first);
    const node = nodeWorkflowOf(second, "uzel");
    expect(node.blocks.map((b) => [b.number, b.title])).toEqual([
      ["1", "Mřížka"],
      ["2", "Řádek"],
    ]);
    expect(node.rules.map((r) => r.text)).toEqual(["Musí platit A", "Nesmí C"]);
    expect(nodeWorkflowOf(second, "jiny").blocks).toEqual([]);
  });

  it("prvek bez invariant pravidla karty nemění", () => {
    const next = insertBlockFromItem("uzel", fixture({ invariants: [] }))(emptyDesktopState());
    expect(nodeWorkflowOf(next, "uzel").rules).toEqual([]);
  });
});
