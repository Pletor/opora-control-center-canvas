import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import LinieTrialSteps from "./LinieTrialSteps";

describe("Jak vyzkoušet", () => {
  it("vykreslí očíslované kroky, bez kroků nic", () => {
    const html = renderToStaticMarkup(createElement(LinieTrialSteps, { steps: ["Otevři Linii", "Uvidíš kuličku"] }));
    expect(html).toContain("Jak vyzkoušet");
    expect(html).toContain("<ol class=\"linie-trial__steps\"><li>Otevři Linii</li><li>Uvidíš kuličku</li></ol>");
    expect(renderToStaticMarkup(createElement(LinieTrialSteps, { steps: [] }))).toBe("");
  });
});
