import { describe, expect, it } from "vitest";
import { emptyDesktopState, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import {
  blockFromItem,
  cardFromItem,
  insertBlockFromItem,
  purposeFromItem,
  templateReference,
  TEMPLATE_BLOCK_TITLE,
  workflowFromItem,
} from "./catalog-insert";
import { itemById, type CatalogItem } from "./library-catalog";

/** Zkušební položka: základ, ke kterému se v testu dopisuje jen to, co se zkouší. */
const fixture = (patch: Partial<CatalogItem> = {}): CatalogItem => ({
  id: "fixture",
  category: "fe-components",
  label: "Zkušební položka",
  hint: "Jen pro test",
  icon: "×",
  kind: "card",
  rules: { must: ["Musí platit A", "Musí platit B"], mustNot: ["Nesmí C"] },
  decomposition: [
    { title: "Dílek", text: "Jedno pole" },
    { title: "Logika", text: "Čistá funkce" },
  ],
  template: "// logic/form-model.ts\nexport function validate() {}",
  ...patch,
});

describe("catalog-insert – karta z položky", () => {
  it("jméno je popisek, účel nese nápovědu i odkaz ze šablony", () => {
    const card = cardFromItem(fixture(), "sektor", 120.4, 40.6);
    expect(card.kind).toBe("node");
    expect(card.parentId).toBe("sektor");
    expect(card.name).toBe("Zkušební položka");
    expect(card.purpose).toBe("Jen pro test · logic/form-model.ts");
    expect({ x: card.x, y: card.y }).toEqual({ x: 120, y: 41 });
    expect(card.id).not.toBe(cardFromItem(fixture(), null, 0, 0).id);
  });

  it("odkaz na šablonu je první neprázdný řádek bez značky komentáře", () => {
    expect(templateReference("\n\n  # backend/editor/node/node_text.py\nx = 1")).toBe("backend/editor/node/node_text.py");
    expect(templateReference(".blok__prvek {\n  color: red;\n}")).toBe(".blok__prvek {");
    expect(templateReference("   ")).toBe("");
    expect(purposeFromItem(fixture({ hint: "", template: "" }))).toBe("");
  });
});

describe("catalog-insert – stav uzlu z položky", () => {
  it("rozpad se stane očíslovanými bloky a šablona posledním blokem", () => {
    const workflow = workflowFromItem(fixture());
    expect(workflow.blocks.map((b) => [b.number, b.title])).toEqual([
      ["1", "Dílek"],
      ["2", "Logika"],
      ["3", TEMPLATE_BLOCK_TITLE],
    ]);
    expect(workflow.blocks[0].text).toBe("Jedno pole");
    expect(workflow.blocks[2].text).toBe("// logic/form-model.ts\nexport function validate() {}");
    expect(workflow.blocks.every((b) => b.parentBlockId === "")).toBe(true);
    expect(new Set(workflow.blocks.map((b) => b.id)).size).toBe(3);
  });

  it("musí a nesmí se stanou pravidly uzlu ve stejném pořadí", () => {
    const workflow = workflowFromItem(fixture());
    expect(workflow.rules.map((r) => [r.kind, r.text])).toEqual([
      ["must", "Musí platit A"],
      ["must", "Musí platit B"],
      ["must_not", "Nesmí C"],
    ]);
    expect(workflow.phase).toBe("discover");
    expect(workflow.actions).toEqual([]);
    expect(workflow.materials).toEqual([]);
    expect(workflow.done.confirmed).toBe(false);
  });

  it("vydaná položka „Formulář s validací“ dá kartu s rozpadem i pravidly", () => {
    const item = itemById("fe-form-validated");
    expect(item).not.toBeNull();
    const workflow = workflowFromItem(item!);
    expect(workflow.blocks.length).toBe(item!.decomposition.length + 1);
    expect(workflow.blocks.at(-1)?.title).toBe(TEMPLATE_BLOCK_TITLE);
    expect(workflow.rules.length).toBe(item!.rules.must.length + item!.rules.mustNot.length);
  });
});

describe("catalog-insert – blok z položky", () => {
  it("nadpis je popisek, text šablona a kategorie zůstane štítkem", () => {
    const block = blockFromItem(fixture({ kind: "block", category: "fe-css", label: "Mřížka", template: ".m { display: grid; }" }));
    expect(block.title).toBe("Mřížka");
    expect(block.text).toBe(".m { display: grid; }");
    expect(block.tags).toEqual(["fe-css"]);
    expect(block.state.status).toBe("open");
  });

  it("vložení do vybrané karty doplní blok na konec a přečísluje", () => {
    const item = fixture({ kind: "block", label: "Mřížka", category: "fe-css" });
    const first = insertBlockFromItem("uzel", item)(emptyDesktopState());
    const second = insertBlockFromItem("uzel", fixture({ kind: "block", label: "Řádek" }))(first);
    expect(nodeWorkflowOf(second, "uzel").blocks.map((b) => [b.number, b.title])).toEqual([
      ["1", "Mřížka"],
      ["2", "Řádek"],
    ]);
    expect(nodeWorkflowOf(second, "uzel").blocks[0].tags).toEqual(["fe-css"]);
    // Stav uzlu se nepřepisuje: co v něm bylo, zůstává (jiné uzly se nedotknou vůbec).
    expect(nodeWorkflowOf(second, "jiny").blocks).toEqual([]);
  });
});
