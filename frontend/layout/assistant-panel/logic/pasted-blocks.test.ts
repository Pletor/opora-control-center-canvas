import { describe, expect, it } from "vitest";
import { composeMessage, isLongPaste, newBlock, pastePreview, splitMessage, withBlockText } from "./pasted-blocks";

describe("vložený text jako dlaždice", () => {
  it("dlouhé nebo víceřádkové vložení je dlaždice, krátké ne", () => {
    expect(isLongPaste("ahoj")).toBe(false);
    expect(isLongPaste("x".repeat(1500))).toBe(true);
    expect(isLongPaste("a\n".repeat(20))).toBe(true);
  });

  it("náhled je začátek bez zalomení", () => {
    expect(pastePreview("Ample\n\nLab  platforma")).toBe("Ample Lab platforma");
    expect(pastePreview("x".repeat(300))).toHaveLength(141);
  });

  it("zpráva má pokyn první a dlaždice v označených blocích", () => {
    const blocks = [newBlock("zadání A"), newBlock("zadání B")];
    expect(composeMessage("/wayfinder rozlož", blocks)).toBe(
      '/wayfinder rozlož\n\n<vlozeny_text cislo="1">\nzadání A\n</vlozeny_text>\n\n<vlozeny_text cislo="2">\nzadání B\n</vlozeny_text>',
    );
    expect(composeMessage("  jen text ", [])).toBe("jen text");
    expect(composeMessage("", [blocks[0]])).toBe('<vlozeny_text cislo="1">\nzadání A\n</vlozeny_text>');
  });

  it("tužka přidá text dlaždice za napsaný text", () => {
    const block = newBlock("zadání");
    expect(withBlockText("", block)).toBe("zadání");
    expect(withBlockText("pokyn  \n", block)).toBe("pokyn\n\nzadání");
  });

  it("odeslaná zpráva se rozloží zpět na pokyn a vložené texty", () => {
    const message = composeMessage("/wayfinder rozlož", [newBlock("A\n\nřádek"), newBlock("B")]);
    expect(splitMessage(message)).toEqual({ text: "/wayfinder rozlož", blocks: ["A\n\nřádek", "B"] });
    expect(splitMessage("obyčejná zpráva")).toEqual({ text: "obyčejná zpráva", blocks: [] });
  });

  it("každá dlaždice má vlastní id", () => {
    expect(newBlock("a").id).not.toBe(newBlock("a").id);
  });
});
