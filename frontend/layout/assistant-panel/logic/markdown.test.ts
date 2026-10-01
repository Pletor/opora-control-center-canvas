import { describe, expect, it } from "vitest";
import { parseInline, parseMarkdown } from "./markdown";

describe("bloky", () => {
  it("rozezná nadpisy a odstavce oddělené prázdným řádkem", () => {
    const blocks = parseMarkdown("# Plán\n\nPrvní věta\ndruhý řádek\n\n### Detail");
    expect(blocks).toEqual([
      { type: "heading", level: 1, children: [{ type: "text", text: "Plán" }] },
      { type: "paragraph", children: [{ type: "text", text: "První věta" }, { type: "break" }, { type: "text", text: "druhý řádek" }] },
      { type: "heading", level: 3, children: [{ type: "text", text: "Detail" }] },
    ]);
  });

  it("nadpis pátého a šestého stupně zmenší na čtvrtý", () => {
    expect(parseMarkdown("###### malý")[0]).toMatchObject({ type: "heading", level: 4 });
  });

  it("blok kódu drží text doslova včetně hvězdiček a HTML", () => {
    const blocks = parseMarkdown("Před\n```ts\nconst a = **b** <i>;\n```\nPo");
    expect(blocks[1]).toEqual({ type: "code", lang: "ts", text: "const a = **b** <i>;" });
    expect(blocks[2]).toEqual({ type: "paragraph", children: [{ type: "text", text: "Po" }] });
  });

  it("neuzavřený blok kódu během streamování běží do konce textu", () => {
    expect(parseMarkdown("```\nřádek 1\nřádek 2")).toEqual([{ type: "code", lang: "", text: "řádek 1\nřádek 2" }]);
  });

  it("odrážky a číslované seznamy, i s víceřádkovou položkou", () => {
    const blocks = parseMarkdown("- jedna\n  pokračuje\n- dvě\n\n3. tři\n4. čtyři");
    expect(blocks[0]).toEqual({
      type: "list",
      ordered: false,
      start: 1,
      items: [
        { depth: 0, children: [{ type: "text", text: "jedna" }, { type: "break" }, { type: "text", text: "pokračuje" }] },
        { depth: 0, children: [{ type: "text", text: "dvě" }] },
      ],
    });
    expect(blocks[1]).toMatchObject({ type: "list", ordered: true, start: 3, items: [{ depth: 0 }, { depth: 0 }] });
  });

  it("číslovaný seznam s prázdnými řádky mezi položkami zůstane jeden", () => {
    const blocks = parseMarkdown("1. a\n\n2. b\n\n3. c");
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ type: "list", items: [{}, {}, {}] });
  });

  it("vnořená odrážka dostane hloubku 1", () => {
    const blocks = parseMarkdown("1. hlavní\n   - pod\n2. další");
    expect(blocks[0]).toMatchObject({ type: "list", ordered: true, items: [{ depth: 0 }, { depth: 1 }, { depth: 0 }] });
  });

  it("oddělovač --- a citace", () => {
    expect(parseMarkdown("a\n\n---\n\n> pozor")).toEqual([
      { type: "paragraph", children: [{ type: "text", text: "a" }] },
      { type: "rule" },
      { type: "quote", children: [{ type: "text", text: "pozor" }] },
    ]);
  });

  it("nebezpečné HTML zůstane textem", () => {
    const blocks = parseMarkdown('<script>alert(1)</script>\n<img src=x onerror="x">');
    expect(blocks).toEqual([
      {
        type: "paragraph",
        children: [{ type: "text", text: "<script>alert(1)</script>" }, { type: "break" }, { type: "text", text: '<img src=x onerror="x">' }],
      },
    ]);
  });

  it("prázdný text nedá žádný blok", () => {
    expect(parseMarkdown("")).toEqual([]);
    expect(parseMarkdown("\n \n")).toEqual([]);
  });
});

describe("inline", () => {
  it("tučně, kurzíva a kód", () => {
    expect(parseInline("a **b** *c* `d`")).toEqual([
      { type: "text", text: "a " },
      { type: "strong", children: [{ type: "text", text: "b" }] },
      { type: "text", text: " " },
      { type: "em", children: [{ type: "text", text: "c" }] },
      { type: "text", text: " " },
      { type: "code", text: "d" },
    ]);
  });

  it("kurzíva uvnitř tučného", () => {
    expect(parseInline("**velmi *důležité* věc**")).toEqual([
      {
        type: "strong",
        children: [{ type: "text", text: "velmi " }, { type: "em", children: [{ type: "text", text: "důležité" }] }, { type: "text", text: " věc" }],
      },
    ]);
  });

  it("kód nic uvnitř neformátuje", () => {
    expect(parseInline("`**x**`")).toEqual([{ type: "code", text: "**x**" }]);
  });

  it("neuzavřený ** během streamování zůstane textem", () => {
    expect(parseInline("začátek **rozepsan")).toEqual([{ type: "text", text: "začátek **rozepsan" }]);
    expect(parseMarkdown("- **pol")).toEqual([
      { type: "list", ordered: false, start: 1, items: [{ depth: 0, children: [{ type: "text", text: "**pol" }] }] },
    ]);
  });

  it("neuzavřený backtick zůstane textem", () => {
    expect(parseInline("a `b")).toEqual([{ type: "text", text: "a `b" }]);
  });

  it("hvězdička obklopená mezerami není kurzíva", () => {
    expect(parseInline("2 * 3 * 4")).toEqual([{ type: "text", text: "2 * 3 * 4" }]);
  });

  it("podtržítko uvnitř slova není kurzíva", () => {
    expect(parseInline("node_brief_v2")).toEqual([{ type: "text", text: "node_brief_v2" }]);
  });

  it("odkaz zůstane textem s adresou", () => {
    expect(parseInline("viz [docs](https://x.cz/a)")).toEqual([
      { type: "text", text: "viz " },
      { type: "link", text: "docs", href: "https://x.cz/a" },
    ]);
  });

  it("zpětné lomítko ruší značku", () => {
    expect(parseInline("\\*ne\\*")).toEqual([{ type: "text", text: "*ne*" }]);
  });
});
