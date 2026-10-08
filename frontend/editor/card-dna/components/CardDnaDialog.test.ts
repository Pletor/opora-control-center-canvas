import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import CardDnaDialog from "./CardDnaDialog";

describe("CardDnaDialog", () => {
  it("má sedm ARIA záložek a renderuje jen aktivní obsah", () => {
    const html = renderToStaticMarkup(createElement(CardDnaDialog, {
      title: "GOAL", onClose: () => {}, overview: "Co po tobě chci", spec: "tajné zadání",
    }));
    expect((html.match(/role="tab"/g) ?? [])).toHaveLength(7);
    expect(html).toContain("Co po tobě chci");
    expect(html).not.toContain("tajné zadání");
  });
});
