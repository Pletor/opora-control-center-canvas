import { describe, expect, it } from "vitest";
import { explainView } from "./heart-explain";

describe("explainView", () => {
  it("aktivní zarážky nahoře, uzly v sekundách, dávky nejnovější první", () => {
    const v = explainView({
      now: { state: "sleeping", sentence: "Spí do 12:00." },
      stops: [{ id: "a", label: "A", active: false }, { id: "b", label: "B", active: true, lever: "x" }],
      pipeline: [{ run: "r1", status: "ok", nodes: [{ node: "n", label: "Sběr", ms: 1500, error: null }, { node: "m", label: "Běh", ms: null, error: null }] }],
      batches: [{ at: "1", headline: "první", phases: [{ id: "p", label: "P", ms: 2000, share: 0.5 }] }, { at: "2", headline: "druhá" }],
      queue: [{ type: "t", ref: "r", workspace: "w", dueInS: 4.6 }],
    });
    expect(v.now.sentence).toBe("Spí do 12:00.");
    expect(v.stops.rows.map((s) => s.id)).toEqual(["b", "a"]);
    expect(v.pipeline.runs[0].line).toBe("Sběr 2 s → Běh běží");
    expect(v.batches.rows.map((b) => b.at)).toEqual(["2", "1"]);
    expect(v.batches.rows[1].phases[0]).toMatchObject({ percent: 50, seconds: "2 s" });
    expect(v.queue.rows[0].dueIn).toBe("5");
  });
  it("souběžné volání je označené, protože sdílí čas skupiny", () => {
    const v = explainView({ batches: [{ at: "1", slowest: [{ tool: "opora_heart.py intake", ms: 218000, category: "opora_write", parallel: true }] }] });
    expect(v.batches.rows[0].slowest[0]).toBe("opora_heart.py intake 218 s (opora_write, souběžně)");
  });
  it("pomalý požadavek serveru řekne čas, cestu a trvání", () => {
    const v = explainView({ slow: [{ at: "2026-11-13T01:42:21Z", method: "POST", path: "/api/brain/heart/brief", ms: 60400, status: 200 }] });
    expect(v.slow.rows).toEqual(["01:42:21 POST /api/brain/heart/brief 60 s (200)"]);
  });
  it("chyba jedné sekce neshodí ostatní", () => {
    const v = explainView({ now: { error: "x" }, stops: [{ id: "a", active: true }] });
    expect(v.now.error).toContain("x");
    expect(v.stops.error).toBe("");
    expect(v.stops.rows).toHaveLength(1);
  });
});
