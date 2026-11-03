import { expect, it } from "vitest";
import { parseInline, parseMarkdown, safeHref } from "./markdown";

it("parses the blocks of a brand book", () => {
  const blocks = parseMarkdown("# Ember\n\nKrátké věty,\nbez vykřičníků.\n\n- jedna\n- dvě\n\n1. první\n2) druhá\n\n> Hlas je klidný.\n\n```css\n.a { }\n```\n\n---\n## Barvy");
  expect(blocks.map((block) => block.kind)).toEqual(["heading", "paragraph", "list", "list", "quote", "code", "rule", "heading"]);
  expect(blocks[1]).toEqual({ kind: "paragraph", inline: [{ kind: "text", text: "Krátké věty, bez vykřičníků." }] });
  expect(blocks[2]).toMatchObject({ ordered: false, items: [[{ text: "jedna" }], [{ text: "dvě" }]] });
  expect(blocks[3]).toMatchObject({ ordered: true });
  expect(blocks[5]).toEqual({ kind: "code", text: ".a { }" });
  expect(blocks[7]).toMatchObject({ kind: "heading", level: 2 });
});

it("parses inline code, bold, italic and only safe links", () => {
  expect(parseInline("Text `ink` na **surface**, *nikdy* [web](https://example.cz) a [zlo](javascript:alert(1))")).toEqual([
    { kind: "text", text: "Text " }, { kind: "code", text: "ink" }, { kind: "text", text: " na " }, { kind: "strong", text: "surface" },
    { kind: "text", text: ", " }, { kind: "em", text: "nikdy" }, { kind: "text", text: " " }, { kind: "link", text: "web", href: "https://example.cz" },
    { kind: "text", text: " a " }, { kind: "text", text: "zlo" }, { kind: "text", text: ")" },
  ]);
  expect(safeHref("javascript:alert(1)")).toBeNull();
  expect(safeHref("data:text/html,x")).toBeNull();
  expect(safeHref("#barvy")).toBe("#barvy");
  expect(safeHref("docs/a.md")).toBe("docs/a.md");
});
