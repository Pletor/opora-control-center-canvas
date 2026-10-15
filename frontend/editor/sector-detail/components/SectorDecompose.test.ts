import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import SectorDecompose from "./SectorDecompose";

const base = { project: "ample", workspace: "draft", sectorId: "sec-4", sectorName: "4. VRSTVA", purpose: "Retrieval", cards: 3 };
const render = (spec: { goal: string; acceptance: string } | null) => renderToStaticMarkup(createElement(SectorDecompose, { ...base, spec }));

describe("SectorDecompose", () => {
  it("před načtením zadání jen hlásí načítání, bez textarea a bez Kopírovat", () => {
    const html = render(null);
    expect(html).toContain("Načítám uložené zadání sektoru…");
    expect(html).not.toContain("sector-decompose-missing");
    expect(html).not.toContain("sector-decompose-prompt");
    expect(html).not.toContain("Kopírovat zadání");
  });

  const cases: [string, { goal: string; acceptance: string }, string][] = [
    ["chybí jen cíl", { goal: "  ", acceptance: "Hotovo, když vrátí top 5." }, "Sektor nemá uložený podklad: cíl práce."],
    ["chybí jen akceptace", { goal: "Správná služba v top 5.", acceptance: "" }, "Sektor nemá uložený podklad: podmínky dokončení."],
    ["akceptace jen z mezer", { goal: "Správná služba v top 5.", acceptance: " \n " }, "Sektor nemá uložený podklad: podmínky dokončení."],
    ["chybí obojí", { goal: "", acceptance: "" }, "Sektor nemá uložený podklad: cíl práce a podmínky dokončení."],
  ];
  it.each(cases)("%s: pojmenuje právě chybějící podklad, bez pole zadání i bez Kopírovat", (_name, spec, message) => {
    const html = render(spec);
    expect(html).toContain(message);
    expect(html).not.toContain("sector-decompose-prompt");
    expect(html).not.toContain("sector-decompose-copy");
    expect(html).not.toContain("/opora-control-center");
  });

  it("s uloženým cílem i akceptací nabídne zadání jen ke čtení s obsahem pro rozkladače a tlačítko Kopírovat", () => {
    const html = render({ goal: "Správná služba v top 5.", acceptance: "Hotovo, když vrátí top 5." });
    expect(html).toContain('data-testid="sector-decompose-prompt"');
    expect(html).toContain('aria-label="Zadání pro agenta-rozkladače sektoru"');
    expect(html).toMatch(/<textarea[^>]*readonly/i);
    expect(html).toContain("Jsi rozkladač sektoru. Projekt ample, workspace draft, sektor id sec-4.");
    expect(html).toContain("Název sektoru: 4. VRSTVA");
    expect(html).toContain('data-testid="sector-decompose-copy"');
    expect(html).toContain("Sektor má 3 karty");
    expect(html).not.toContain("Sektor nemá uložený podklad");
  });

  it("nepovolený identifikátor: hláška o identifikátoru, bez pole i bez Kopírovat", () => {
    const html = renderToStaticMarkup(createElement(SectorDecompose, { ...base, sectorId: "sec 4", spec: { goal: "Cíl", acceptance: "Hotovo" } }));
    expect(html).toContain("Zadání nejde sestavit");
    expect(html).not.toContain("sector-decompose-prompt");
    expect(html).not.toContain("sector-decompose-copy");
  });
});
