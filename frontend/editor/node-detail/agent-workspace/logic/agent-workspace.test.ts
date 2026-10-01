import { describe, expect, it } from "vitest";
import {
  MAX_SECTION,
  SECTIONS,
  clampSection,
  emptyWorkspace,
  sectionLink,
} from "./agent-workspace";

describe("agent-workspace", () => {
  it("SECTIONS drží pět klíčů ve stanoveném pořadí s českými popisky", () => {
    expect(SECTIONS.map((s) => s.key)).toEqual(["frame", "log", "failures", "fixes", "handoff"]);
    expect(SECTIONS.map((s) => s.label)).toEqual([
      "Rámec a směr",
      "Postup",
      "Co se nepovedlo",
      "Úspěšné opravy",
      "Předávka",
    ]);
  });

  it("nápověda předávky je přesný text z kontraktu", () => {
    const handoff = SECTIONS.find((s) => s.key === "handoff");
    expect(handoff?.hint).toBe(
      "Konkrétní kroky: kam se podívat, který soused nebo potomek nese souvislost, kudy podle vazeb pokračovat.",
    );
  });

  it("každá sekce má neprázdnou nápovědu", () => {
    for (const s of SECTIONS) expect(s.hint.length).toBeGreaterThan(0);
  });

  it("emptyWorkspace vrátí prázdné sekce, prázdné updatedAt a by human", () => {
    expect(emptyWorkspace()).toEqual({
      frame: "", log: "", failures: "", fixes: "", handoff: "", updatedAt: "", by: "human",
    });
  });

  it("sectionLink poskládá opora:// odkaz s ID uzlu a kotvou sekce", () => {
    expect(sectionLink("node-1", "handoff")).toBe("opora://agent-workspace/node-1#handoff");
    expect(sectionLink("sektor-2", "frame")).toBe("opora://agent-workspace/sektor-2#frame");
  });

  it("MAX_SECTION je 12000 jako na backendu", () => {
    expect(MAX_SECTION).toBe(12000);
  });

  it("clampSection nechá krátký text beze změny", () => {
    expect(clampSection("krátký text")).toBe("krátký text");
  });

  it("clampSection nechá text přesně na limitu beze změny", () => {
    const text = "a".repeat(MAX_SECTION);
    expect(clampSection(text)).toBe(text);
    expect(clampSection(text).length).toBe(MAX_SECTION);
  });

  it("clampSection ořízne text delší než limit", () => {
    const text = "a".repeat(MAX_SECTION + 50);
    const clamped = clampSection(text);
    expect(clamped.length).toBe(MAX_SECTION);
    expect(clamped).toBe("a".repeat(MAX_SECTION));
  });
});
