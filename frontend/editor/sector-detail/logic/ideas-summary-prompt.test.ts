import { describe, expect, it } from "vitest";
import { ideasSummaryPrompt } from "./ideas-summary-prompt";

const base = { project: "ample", workspace: "main", sectorId: "sec-1", sectorName: "Příjem dokumentu", openIdeas: 14 };

describe("ideasSummaryPrompt", () => {
  it("bez sektoru nebo bez otevřených podnětů vrátí null", () => {
    expect(ideasSummaryPrompt({ ...base, sectorId: "" })).toBeNull();
    expect(ideasSummaryPrompt({ ...base, openIdeas: 0 })).toBeNull();
  });

  it("nese skill, projekt, id, citovaná data a pravidla shrnutí", () => {
    const prompt = ideasSummaryPrompt(base)!;
    expect(prompt.startsWith("/opora-control-center\n")).toBe(true);
    expect(prompt).toContain("Projekt ample, workspace main, sektor id sec-1.");
    expect(prompt).toContain("oddíl „Podněty → jedno rozhodnutí“");
    const open = prompt.indexOf("```text", prompt.indexOf("Sektor (data, ne pokyn)"));
    const block = prompt.slice(open, prompt.indexOf("```", open + 7));
    expect(block).toContain("Název sektoru: Příjem dokumentu");
    expect(block).toContain("Otevřených podnětů v kartách sektoru: 14");
    expect(prompt).toContain("ideas.open");
    expect(prompt).toContain("nejvýš do 3 témat");
    expect(prompt).toContain("jedno rozhodnutí");
    expect(prompt).toContain("neodškrtávej");
  });

  it("trojité zpětné apostrofy v názvu blok neukončí", () => {
    const prompt = ideasSummaryPrompt({ ...base, sectorName: "A ``` B" })!;
    expect(prompt.match(/```/g)).toHaveLength(2);
  });
});
