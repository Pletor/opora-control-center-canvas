import { describe, expect, it, vi } from "vitest";
import { adoptScan, withCaptureInspiration, type AdoptDeps } from "./adopt-scan";
import type { ScanProposal } from "./page-scan";

const box = { x: 0, y: 0, w: 12, h: 2 };
const proposal: ScanProposal = {
  sections: [{ id: "hero", role: "hero", name: "Úvod", intent: "Proč tu zůstat", status: "proposed", box, selector: "#hero", look: "tmavé" },
    { id: "cta", role: "cta", name: "Výzva", intent: "", status: "proposed", box: { ...box, y: 2 } }],
  logic: [{ ref: "buy", kind: "action", name: "Koupit", purpose: "", section: "cta", flow: { inputs: ["Košík"], steps: ["Zaplatit"], outputs: [], conditions: [], dataTo: ["Platební brána"] } },
    { ref: "who", kind: "actor", name: "Člen", purpose: "", section: null }],
  screenshot: null, design: { color: { tokens: [{ name: "primary", value: "#f00" }] } }, captures: { page: "page.png", sections: { hero: "hero.png", cta: "cta.png" } }, notes: [],
};
const all = { layout: true, design: true, logic: true };

function deps(overrides: Partial<AdoptDeps> = {}): AdoptDeps {
  return { contentLock: null, saveLayout: vi.fn(async () => undefined), saveInspirations: vi.fn(async (files) => files.size),
    uploadCapture: vi.fn(async (name) => "f-" + name), saveTokens: vi.fn(async () => ({ changes: 1, notes: [] })),
    insertLogic: vi.fn(async (logic: unknown[]) => logic.map((_: unknown, index: number) => "n" + index)), createFlow: vi.fn(async () => true), ...overrides };
}

describe("převzetí návrhu skenu po částech", () => {
  it("vše: layout bez selektoru a bez výřezů, výřezy až samostatným zápisem, tokeny, prvky a plátno toku jen u prvku s flow", async () => {
    const fake = deps();
    const results = await adoptScan(proposal, all, fake);
    const sections = vi.mocked(fake.saveLayout).mock.calls[0][0];
    expect(sections[0]).not.toHaveProperty("selector");
    expect(sections[0]).toMatchObject({ look: "tmavé" });
    expect(sections[0]).not.toHaveProperty("inspiration");
    expect(vi.mocked(fake.saveInspirations).mock.calls[0][0]).toEqual(new Map([["hero", "f-hero.png"], ["cta", "f-cta.png"]]));
    expect(fake.createFlow).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fake.createFlow).mock.calls[0].slice(0, 2)).toEqual(["n0", "Koupit"]);
    expect(results.map((result) => [result.part, result.ok])).toEqual([["layout", true], ["inspiration", true], ["page", false], ["tokens", true], ["logic", true], ["flows", true]]);
  });
  it("na mainu se převezme layout a tokeny, výřezy a logika ne a věta řekne proč", async () => {
    const fake = deps({ contentLock: "Git main je jen ke čtení." });
    const results = await adoptScan(proposal, all, fake);
    expect(fake.uploadCapture).not.toHaveBeenCalled();
    expect(fake.insertLogic).not.toHaveBeenCalled();
    expect(results.filter((result) => !result.ok).map((result) => result.text)).toEqual([
      "Výřezy boxů se nepřevzaly: Git main je jen ke čtení.", "Snímek celé stránky zůstává jen v návrhu: stránka zatím nemá vlastní inspiraci.",
      "Logika a tok dat se nepřevzaly: Git main je jen ke čtení."]);
    expect(results.find((result) => result.part === "layout")?.ok).toBe(true);
  });
  it("selhání jedné části nezahodí ostatní; bez layoutu jdou výřezy do současných boxů", async () => {
    const fake = deps({ saveLayout: vi.fn(async () => { throw new Error("409"); }), saveTokens: vi.fn(async () => { throw new Error("konflikt revize"); }),
      uploadCapture: vi.fn(async (name: string) => { if (name === "cta.png") throw new Error("404"); return "f-" + name; }) });
    const results = await adoptScan(proposal, all, fake);
    expect(vi.mocked(fake.saveInspirations).mock.calls[0][0]).toEqual(new Map([["hero", "f-hero.png"]]));
    expect(results.map((result) => [result.part, result.ok])).toEqual([["inspiration", false], ["layout", false], ["inspiration", true], ["page", false],
      ["tokens", false], ["logic", true], ["flows", true]]);
  });
  it("jen zaškrtnuté části", async () => {
    const fake = deps();
    const results = await adoptScan(proposal, { layout: false, design: false, logic: true }, fake);
    expect(fake.saveLayout).not.toHaveBeenCalled();
    expect(fake.uploadCapture).not.toHaveBeenCalled();
    expect(results.map((result) => result.part)).toEqual(["logic", "flows"]);
  });
  it("výřez se do inspirace nezdvojí", () => {
    const sections = [{ id: "a", role: "hero" as const, name: "A", intent: "", box, inspiration: { files: ["f1"] } }];
    expect(withCaptureInspiration(sections, new Map([["a", "f1"]]))[0].inspiration).toEqual({ files: ["f1"] });
  });
});
