import { describe, expect, it } from "vitest";
import { layoutOfProposal, normalizeScan } from "./page-scan";

describe("odpověď skenu webu", () => {
  it("běží, selhal, neznámý stav", () => {
    expect(normalizeScan({ state: "running" })).toEqual({ state: "running" });
    expect(normalizeScan({ state: "failed", error: "Web neodpověděl" })).toEqual({ state: "failed", error: "Web neodpověděl" });
    expect(normalizeScan({ state: "failed" })).toMatchObject({ state: "failed" });
    expect(normalizeScan(null)).toMatchObject({ state: "failed", error: expect.stringMatching(/neznámý/) });
    expect(normalizeScan({ state: "done" })).toMatchObject({ state: "failed", error: expect.stringMatching(/box/) });
  });
  it("hotový návrh: sekce jako proposed, role a název doplněné, box v mezích, rodič jen v návrhu", () => {
    const result = normalizeScan({ state: "done", cost: 0.04, proposal: {
      sections: [
        { id: "head", role: "header", name: "Hlavička", intent: "Logo", box: { x: 0, y: 0, w: 99, h: 2 } },
        { id: "head", role: "hero", name: "Duplicitní" },
        { id: "bad id!", role: "hero" },
        { id: "nav", role: "menu", parent: "head", box: { x: 0, y: 0, w: 6, h: 1 } },
        { id: "lost", role: "cta", name: "Výzva", parent: "nikde" },
      ],
      logic: [
        { ref: "buy", kind: "action", name: "Koupit", purpose: "Platba", section: "lost" },
        { kind: "actor", section: "neznámý" },
        { kind: "page", name: "Zakázaný druh" },
      ],
      screenshot: "abc",
    } });
    expect(result.state).toBe("done");
    if (result.state !== "done") return;
    expect(result.cost).toBe(0.04);
    expect(result.proposal.screenshot).toBe("abc");
    expect(result.proposal.sections.map((section) => section.id)).toEqual(["head", "nav", "lost"]);
    expect(result.proposal.sections[0]).toMatchObject({ status: "proposed", box: { x: 0, w: 12 }, intent: "Logo" });
    expect(result.proposal.sections[1]).toMatchObject({ role: "custom", name: "Vlastní", parent: "head" });
    expect(result.proposal.sections[2]).not.toHaveProperty("parent");
    expect(result.proposal.sections[2].box).toBeDefined();
    expect(result.proposal.logic).toEqual([
      { ref: "buy", kind: "action", name: "Koupit", purpose: "Platba", section: "lost" },
      { ref: "logic-1", kind: "actor", name: "Uživatel", purpose: "", section: null },
    ]);
  });
  it("překrývající se boxy návrhu se usadí pod sebe, náhled i převzetí stejně", () => {
    const result = normalizeScan({ state: "done", proposal: { sections: [
      { id: "hero", role: "hero", box: { x: 0, y: 0, w: 12, h: 4 } }, { id: "cta", role: "cta", box: { x: 0, y: 2, w: 12, h: 2 }, selector: ".cta" }] } });
    if (result.state !== "done") throw new Error(result.state);
    expect(result.proposal.sections.map((section) => section.box.y)).toEqual([0, 4]);
    expect(layoutOfProposal([{ ...result.proposal.sections[0] }, { ...result.proposal.sections[1], box: { x: 0, y: 1, w: 12, h: 2 } }]).map((section) => section.box.y)).toEqual([0, 4]);
  });
  it("chybějící pole návrhu nevadí", () => {
    const result = normalizeScan({ state: "done", proposal: { sections: [{ id: "a" }], logic: "nic" } });
    expect(result).toMatchObject({ state: "done", cost: null, proposal: { logic: [], screenshot: null, design: null, captures: null, notes: [] } });
  });
  it("verze 6: vzhled, selektor jen pro náhled, tok prvku, snímky a poznámky", () => {
    const long = "x".repeat(200);
    const result = normalizeScan({ state: "done", proposal: {
      sections: [{ id: "hero", role: "hero", intent: "i".repeat(700), look: "tmavé pozadí", selector: "#hero" }, { id: "cta", role: "cta", look: "" }],
      logic: [{ kind: "action", name: "Koupit", flow: { inputs: ["Košík", 3, ""], steps: Array(10).fill("krok"), dataTo: [long] } }, { kind: "form", flow: { inputs: [] } }],
      design: { color: { tokens: [] } }, captures: { page: "page.png", sections: { hero: "hero.png", cta: "../etc/passwd", nikde: "x.png" } }, notes: ["Bez prohlížeče", 5],
    } });
    if (result.state !== "done") throw new Error(result.state);
    const { sections, logic, design, captures, notes } = result.proposal;
    expect(sections[0]).toMatchObject({ look: "tmavé pozadí", selector: "#hero" });
    expect(sections[0].intent).toHaveLength(600);
    expect(sections[1]).not.toHaveProperty("look");
    expect(layoutOfProposal(sections)[0]).not.toHaveProperty("selector");
    expect(logic[0].flow).toEqual({ inputs: ["Košík"], steps: Array(8).fill("krok"), outputs: [], conditions: [], dataTo: ["x".repeat(160)] });
    expect(logic[1]).not.toHaveProperty("flow");
    expect(design).toEqual({ color: { tokens: [] } });
    expect(captures).toEqual({ page: "page.png", sections: { hero: "hero.png" } });
    expect(notes).toEqual(["Bez prohlížeče"]);
  });
});
