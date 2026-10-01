import { describe, expect, it } from "vitest";
import { blockLook, linkChips, resolveTarget, type LinkTarget } from "@/editor/node-detail/content/logic/block-view";

const targets: LinkTarget[] = [
  { id: "n1", name: "Plán vydání", kind: "node" },
  { id: "n2", name: "Sklad", kind: "sector" },
];

describe("vzhled bloku", () => {
  it("mřížky na začátku dělají nadpis, jinde ne", () => {
    expect(blockLook("# Kapitola").heading).toBe(1);
    expect(blockLook("## Sekce").heading).toBe(2);
    expect(blockLook("### Pododdíl").heading).toBe(3);
    expect(blockLook("běžný #hashtag").heading).toBe(0);
    expect(blockLook("#bez mezery").heading).toBe(0);
  });

  it("značka úkolu, hotova, rozhodnutí a důkazu se pozná i uvnitř nadpisu", () => {
    expect(blockLook("TODO zavolat").mark).toBe("todo");
    expect(blockLook("DONE zavoláno").mark).toBe("done");
    expect(blockLook("HOTOVO zavoláno").mark).toBe("done");
    expect(blockLook("ROZHODNUTÍ: jdeme do toho").mark).toBe("decision");
    expect(blockLook("DŮKAZ: soubor.ts:12").mark).toBe("evidence");
    expect(blockLook("## TODO velký úkol")).toEqual({ heading: 2, mark: "todo" });
    expect(blockLook("todo malé písmeno").mark).toBe(null);
    expect(blockLook("").mark).toBe(null);
  });

  it("odkaz se najde podle jména i podle ID, nenalezený zůstane nevyřešený", () => {
    expect(resolveTarget("plán vydání", targets)?.id).toBe("n1");
    expect(resolveTarget("n2", targets)?.name).toBe("Sklad");
    expect(resolveTarget("Nic", targets)).toBe(null);
  });

  it("z bloku vypadnou jen odkazy, v pořadí zápisu", () => {
    expect(linkChips("vazba na [[Sklad]] a [[Neznámý]]", targets)).toEqual([
      { name: "Sklad", id: "n2" },
      { name: "Neznámý", id: null },
    ]);
    expect(linkChips("bez odkazu", targets)).toEqual([]);
  });
});
