import { describe, expect, it } from "vitest";
import type { CardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import { emptyBlock } from "@/editor/node-detail/tree/logic/tree-model";
import { parseCardTrail } from "./card-trail";
import { checkNote, heartReply, judgmentView, ofCount, portViews, remaining, workView } from "./panel-work";

const card = {
  nodeId: "n", stage: "work", health: "ok", reason: "runs_active", executionId: "e2", kind: "task", layer: null, blockedBy: [],
  topoIndex: null, nextActionId: null, gate: null, dod: null, order: 302, pr: null,
  steps: { total: 3, done: 1, current: "s2", items: [{ id: "s1", status: "done", executionId: "e2" },
    { id: "s2", status: "pending", executionId: null }, { id: "s3", status: "pending", executionId: null }] },
} as unknown as CardEntry;

const trail = parseCardTrail({
  nodeId: "n", now: { owner: "agent:office", since: "2026-10-31T10:42:00Z", until: "2026-10-31T12:12:00Z", stepId: "s2" },
  runs: [{ executionId: "e2", owner: "agent:office", createdAt: "2026-10-31T10:42:00Z", state: "running",
    steps: [{ stepId: "s1", title: "Migrace", status: "done", checks: [{ name: "npm test", status: "green" }] },
      { stepId: "s2", title: "Zápis metrik", status: "pending" }] }],
  pr: { number: 40, state: "open" }, missing: ["merged", "human_close"],
});

const judgment = (code: string, stepId: string | null = "s2") =>
  ({ code, stepId, executionId: null, reason: "x", outside: ["a"], source: "det" as const });

describe("panel-work", () => {
  it("práce na kartě: kroky s názvem a kontrolou, další krok, PR, kdo drží a co chybí", () => {
    const work = workView(card, trail);
    expect(work.chip.word).toBe("běží");
    expect(work.stage).toBe("běh");
    expect(work.steps.map((s) => [s.id, s.title, s.glyph, s.note])).toEqual([
      ["s1", "Migrace", "✓", "npm test ✓"], ["s2", "Zápis metrik", "…", "další krok"], ["s3", "s3", "○", ""]]);
    expect(work.next).toBe("s2 · Zápis metrik");
    expect(work.pr).toEqual({ tone: "open", label: "PR #40 otevřené" });
    expect(work.holder).toEqual({ name: "agent:office", until: "2026-10-31T12:12:00Z" });
    expect(work.missing).toEqual(["PR sloučen", "uzavření člověkem"]);
  });

  it("bez agent-state bere kroky z běhů; zaseklá kontrola má přednost před během", () => {
    const stuck = parseCardTrail({ nodeId: "n", now: { owner: "a", since: "x" },
      runs: [{ createdAt: "x", state: "running", steps: [{ stepId: "s1", status: "failed" }] }], judgment: [{ code: "red_twice", stepId: "s1" }] });
    const work = workView(null, stuck);
    expect(work.steps.map((s) => s.tone)).toEqual(["bad"]);
    expect(work.chip.word).toBe("zaseklé");
    expect(workView(null, null).chip.word).toBe("čeká");
  });

  it("poznámka kroku: červená a zelená jménem, bez známého výsledku krátký commit, jinak nic", () => {
    expect(checkNote([{ name: "npm test", status: "green" }, { name: "npm test -- metrics", status: "red" }])).toBe("npm test -- metrics ✗");
    expect(checkNote([{ name: "uv run pytest backend/rag -q: 736 passed", status: "unknown" }, { name: "ruff", status: "green" }])).toBe("ruff ✓");
    expect(checkNote([{ name: "uv run pytest backend/rag -q: 736 passed", status: "green" }])).toBe("uv run pytest backend/r… ✓");
    expect(checkNote([{ name: "a", status: "green" }, { name: "b", status: "green" }])).toBe("2 ✓");
    expect(checkNote([{ name: "uv run pytest", status: "unknown" }], ["8aa15acf77a98b02"])).toBe("8aa15ac");
    expect(checkNote([{ name: "uv run pytest", status: "unknown" }])).toBe("");
  });

  it("věta vedle čipu: krok X z Y, hotovo, zaseklý krok, na co karta čeká; počet commitů a uvolnění", () => {
    expect(workView(card, trail).line).toBe("běh · krok 2 ze 3");
    expect([ofCount(3), ofCount(5), ofCount(7), ofCount(12)]).toEqual(["ze 3", "z 5", "ze 7", "z 12"]);
    const stuck = parseCardTrail({ nodeId: "n", runs: [{ createdAt: "x", state: "reported", steps: [{ stepId: "s2", status: "pending" }] }],
      judgment: [{ code: "red_twice", stepId: "s2" }] });
    const bad = workView(card, stuck);
    expect([bad.line, bad.steps[1].tone, bad.steps[1].note]).toEqual(["s2 · 2× červená", "bad", "2× červená"]);
    const done = parseCardTrail({ nodeId: "n", runs: [{ createdAt: "x", state: "reported", steps: [
      { stepId: "s1", status: "done", commits: ["a1", "b2"] }, { stepId: "s2", status: "done", commits: ["b2"] }] }],
      recent: [{ at: "2026-10-31T12:58:00Z", who: "office", kind: "lease.released" }] });
    const finished = workView(null, done);
    expect([finished.chip.word, finished.line, finished.commits, finished.released, finished.untouched])
      .toEqual(["hotovo", "2/2 kroků", "2 commity", "2026-10-31T12:58:00Z", false]);
    const waiting = workView({ ...card, steps: null } as unknown as CardEntry, null, { waitingFor: ["3·02 Zápis metrik"] });
    expect([waiting.chip.word, waiting.line, waiting.untouched, waiting.commits]).toEqual(["čeká", "na kartu 3·02 Zápis metrik", true, ""]);
    expect(workView(card, trail).untouched).toBe(false);
  });

  it("zbývající čas držení", () => {
    const now = Date.parse("2026-10-31T11:54:00Z");
    expect(remaining("2026-10-31T12:12:00Z", now)).toBe("zbývá 18 min");
    expect(remaining("2026-10-31T11:00:00Z", now)).toBe("vypršelo");
    expect(remaining("2026-10-31T16:00:00Z", now)).toBe("zbývá 4 h");
    expect(remaining(null, now)).toBe("");
  });

  it("úsudek: červená jen u red_twice, jinak zlatá otázka; odkaz do Review nebo Běhu", () => {
    const red = judgmentView(judgment("red_twice"), 0);
    expect([red.tone, red.label, red.link.tab, red.link.text, red.heart]).toEqual(["bad", "2× červená", "run", "Výstup kontroly →", ""]);
    const files = judgmentView(judgment("files_mismatch"), 1);
    expect([files.tone, files.label, files.link.tab, files.outside]).toEqual(["gold", "jiné soubory", "review", ["a"]]);
    expect(judgmentView(judgment("neznámý", null), 2)).toMatchObject({ label: "neznámý", tone: "gold", where: "" });
  });

  it("odpověď srdci nese kartu, příznak a krok", () => {
    expect(heartReply({ id: "n", name: "Zápis metrik" }, judgment("files_mismatch"), " Patří sem. "))
      .toBe("Karta „Zápis metrik“ (n), příznak files_mismatch u kroku s2: Patří sem.");
  });

  it("port: popisek z portu bloku, ze kterého vazba vede", () => {
    const block = { ...emptyBlock(), id: "b", ports: [{ id: "p", label: "metriky" }] };
    const ports = portViews([
      { edgeId: "e1", targetId: "n1", targetName: "Dashboard", summary: "Schéma", handoff: "", by: "office", updatedAt: null, source: "agent" },
      { edgeId: "e2", targetId: "n2", targetName: null, summary: "", handoff: "", by: "", updatedAt: null, source: "det" }],
      [{ id: "e1", source: "n", target: "n1", port: "block", sourceBlockId: "b", sourcePortId: "p" }], [block]);
    expect(ports.map((p) => [p.label, p.target])).toEqual([["metriky", "Dashboard"], ["vazba", "n2"]]);
  });
});
