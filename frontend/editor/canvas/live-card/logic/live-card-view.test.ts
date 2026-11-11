import { describe, expect, it } from "vitest";
import type { OporaEvent } from "@/editor/live-strip/logic/events-client";
import { LIVE_CARD_BARE, LIVE_CARD_FULL } from "./live-card-fixture";
import { parseFuture, parseLiveCard, parseMirror } from "./live-card-types";
import { jsonTokens } from "./json-tokens";
import {
  actorView, costSeries, futureLines, futureVerdict, mirrorBar, mirrorPlace, eventToRecent, mergeRecent, flowColumns, isPending, latestRun, prependRecent, relationView, runLanes, sparkPoints,
  sourcePath, sourceShape, stateView, testSeries, truthBar, usd,
} from "./live-card-view";

describe("live card parser", () => {
  it("keeps the skeleton strict and fills missing sections with null or empty lists", () => {
    expect(() => parseLiveCard({ title: "x" })).toThrow();
    const card = parseLiveCard({ nodeId: "n1", truths: { mirror: { available: false, milestone: "F1" } } });
    expect(card.title).toBe("n1");
    expect(card.edges).toEqual([]);
    expect(card.flow).toBeNull();
    expect(card.truths.vision).toBeNull();
    expect(isPending(card.truths.mirror)).toBe(true);
    expect(parseLiveCard(LIVE_CARD_FULL).linie?.pr).toBe(412);
  });
});

describe("code mirror", () => {
  it("parses both the pending and the measured mirror", () => {
    expect(parseMirror({ available: false, milestone: "F1" })).toEqual({ available: false, milestone: "F1" });
    expect(parseMirror(null)).toBeNull();
    expect(parseMirror({ source: "x" })).toBeNull();
    const mirror = parseMirror({ available: true, source: "/s", items: [{ name: "a", path: "p.py", line: 3, status: "ok", text: "" }, "junk"], counts: { matched: 1 }, evidence: null });
    expect(mirror).toEqual({ available: true, source: "/s", items: [{ name: "a", path: "p.py", line: 3, status: "ok", text: "" }],
      counts: { matched: 1, missing: 0, extra: 0 }, evidence: null });
    expect(parseLiveCard(LIVE_CARD_FULL).truths.mirror).toMatchObject({ available: true, counts: { matched: 2, missing: 1, extra: 1 } });
  });
  it("bar counts matched of expected, extra stays out; place is file:line", () => {
    const mirror = LIVE_CARD_FULL.truths.mirror as Parameters<typeof mirrorBar>[0];
    expect(mirrorBar(mirror)).toEqual({ done: 2, total: 3, pct: 67 });
    expect(mirrorBar({ ...mirror, counts: { matched: 0, missing: 0, extra: 2 } })).toBeNull();
    expect(mirrorPlace(mirror.items[0])).toBe("backend/api/fapi.py:12");
    expect(mirrorPlace(mirror.items[1])).toBe("backend/fapi_sig.py");
  });
});

describe("live card future", () => {
  it("parses only an available future and fills missing lists", () => {
    expect(parseFuture({ available: false })).toBeNull();
    expect(parseFuture({ available: false, milestone: "F4" })).toBeNull();
    const future = parseFuture({ available: true, verdict: "warning", works: [{ branch: "feat/a", target: "main" }, { nope: 1 }] });
    expect(future?.works).toEqual([{ branch: "feat/a", target: "main", changed: [], conflicts: [], impacts: [], overlaps: [] }]);
  });
  it("names verdicts and lists conflicts before impacts and overlaps", () => {
    expect(futureVerdict("blocked")).toEqual({ label: "konflikt", status: "bad" });
    expect(futureVerdict("clean").status).toBe("ok");
    expect(futureVerdict("weird").status).toBe("miss");
    const lines = futureLines({ mark: "OP-A", branch: "feat/a", target: "main", changed: ["a.py"], conflicts: ["a.py"],
      impacts: [{ nodeId: "c", name: "Sklad", via: "shares_code", paths: ["a", "b", "c", "d"] }],
      overlaps: [{ nodeId: "b", mark: null, branch: "feat/b", paths: ["a.py"] }] });
    expect(lines.map(line => [line.status, line.text])).toEqual([["bad", "konflikt a.py"],
      ["wait", "Sklad (sdílí kód) · a, b, c +1"], ["wait", "feat/b mění totéž · a.py"]]);
  });
});

describe("live card view", () => {
  it("names states and truth bars", () => {
    expect(stateView("bud")).toEqual({ label: "Vývoj", tone: "work" });
    expect(stateView("weird").tone).toBe("plain");
    expect(truthBar({ source: "", items: [{ text: "a", status: "ok" }, { text: "b", status: "miss" }] })).toEqual({ done: 1, total: 2, pct: 50 });
    expect(truthBar({ source: "", items: [] })).toBeNull();
    expect(isPending(LIVE_CARD_BARE.truths.mirror)).toBe(true);
    expect(isPending(LIVE_CARD_FULL.truths.vision)).toBe(false);
  });
  it("maps edge relations in Czech and English, shared code is dashed", () => {
    expect(relationView("používá", "out")).toMatchObject({ label: "používá", tone: "work", arrow: "→", dashed: false });
    expect(relationView("requires", "in")).toMatchObject({ label: "vyžaduje", tone: "vision", arrow: "←" });
    expect(relationView("shares_code", "in")).toMatchObject({ label: "sdílí kód", dashed: true, arrow: "⇄" });
    expect(relationView(null, "out")).toMatchObject({ label: "vazba", tone: "plain" });
  });
  it("orders runs by time for sparklines and needs two numbers to draw", () => {
    expect(testSeries(LIVE_CARD_FULL.runs)).toEqual([1 / 6, 1]);
    expect(costSeries(LIVE_CARD_FULL.runs)).toEqual([0.02, 0.04]);
    expect(latestRun(LIVE_CARD_FULL.runs)?.executionId).toBe("x2");
    expect(sparkPoints([1, null])).toBeNull();
    expect(sparkPoints([0, 2], 100, 44)).toBe("0,40 100,6");
    expect(usd(0.163)).toBe("0,16");
    expect(usd(null)).toBe("—");
  });
  it("turns a stream event into a diary row and keeps 30 newest first", () => {
    const event = { id: 9, at: "2026-11-11T14:40:00Z", kind: "step.done", stepId: "s2", actor: { kind: "agent", name: "agent:codex" }, data: {} } as unknown as OporaEvent;
    const row = eventToRecent(event);
    expect(row).toEqual({ at: event.at, actor: "agent:codex", kind: "step.done", text: "s2 hotov", source: "/api/oporahub/events/stream" });
    const office = { ...event, kind: "tool.use", actor: { kind: "agent", name: "Ada" }, title: "Ada: Edit", tool: { target: "a.ts" } };
    expect(eventToRecent(office).text).toBe("Ada: Edit · a.ts");
    expect(eventToRecent({ ...event, kind: "worker.message", title: "Srdce dělníkovi (stop): Stůj." } as typeof event).text).toBe("Srdce dělníkovi (stop): Stůj.");
    const many = Array.from({ length: 40 }, (_, i) => ({ ...row, text: String(i) }));
    const merged = prependRecent(many, [{ ...row, text: "new" }]);
    expect(merged).toHaveLength(30);
    expect(merged[0].text).toBe("new");
    const api = [{ ...row, at: "2026-11-11T14:00:00Z" }];
    expect(mergeRecent(api, [{ ...row, at: "2026-11-11T14:00:00Z", text: "jinak" }, row])).toEqual([row, api[0]]);
  });
  it("puts actors on lanes by time", () => {
    expect(actorView("heart").lane).toBe("Srdce");
    expect(actorView("agent:codex-3").lane).toBe("Dělník");
    // F2: druh rozhodne dřív než jméno; hlídač a trigger z aktéra `card.signal`
    expect(actorView("Ada", "tool.use")).toEqual({ tone: "work", lane: "Dělník" });
    expect(actorView("system", "worker.message.delivered").lane).toBe("Dělník");
    expect(actorView("system", "turn.end").lane).toBe("Dělník");
    expect(actorView("heart", "worker.message")).toEqual({ tone: "heart", lane: "Srdce" });
    expect(actorView("hlídač", "card.signal")).toEqual({ tone: "risk", lane: "Hlídač" });
    expect(actorView("trigger", "card.signal")).toEqual({ tone: "mirror", lane: "Trigger" });
    const monitor = runLanes([
      { at: "2026-11-11T10:00:00Z", actor: "Ada", kind: "tool.use", text: "Ada: Edit · a.ts", source: "x" },
      { at: "2026-11-11T10:01:00Z", actor: "hlídač", kind: "card.signal", text: "card.drift: …", source: "x" },
      { at: "2026-11-11T10:02:00Z", actor: "heart", kind: "worker.message", text: "Srdce dělníkovi (course): …", source: "x" },
      { at: "2026-11-11T10:03:00Z", actor: "Ada", kind: "worker.message.delivered", text: "převzato", source: "x" },
    ]);
    expect(monitor.map(lane => [lane.lane, lane.ticks])).toEqual([["Dělník", [0, 97]], ["Hlídač", [32.3]], ["Srdce", [64.7]]]);
    const lanes = runLanes(LIVE_CARD_FULL.recent);
    expect(lanes.map(lane => lane.lane).sort()).toEqual(["Dělník", "Srdce"]);
    expect(lanes.find(lane => lane.lane === "Srdce")?.ticks).toEqual([97]);
    expect(lanes.find(lane => lane.lane === "Dělník")?.ticks).toEqual([0]);
    expect(runLanes([])).toEqual([]);
  });
  it("reads flow columns from strings or objects", () => {
    const flow = flowColumns(LIVE_CARD_FULL.flow!);
    expect(flow.columns).toEqual([["FAPI"], ["Webhook", "Podpis"], ["payment.paid"]]);
    expect(flow.conditions).toEqual(["podpis platný"]);
    expect(flowColumns({ ...LIVE_CARD_FULL.flow!, inputs: null, steps: [], outputs: undefined, dataTo: null }).empty).toBe(true);
  });
});

describe("json tokens", () => {
  it("splits keys, strings and literals and rebuilds the exact text", () => {
    const value = { id: "a\"b", n: 4.5, ok: true, none: null, list: [1, "x"] };
    const tokens = jsonTokens(value);
    expect(tokens.map(token => token.text).join("")).toBe(JSON.stringify(value, null, 2));
    expect(tokens.filter(token => token.kind === "key").map(token => token.text)).toEqual(['"id"', '"n"', '"ok"', '"none"', '"list"']);
    expect(tokens.filter(token => token.kind === "num").map(token => token.text)).toEqual(["4.5", "true", "null", "1"]);
    expect(tokens.filter(token => token.kind === "str").map(token => token.text)).toEqual(['"a\\"b"', '"x"']);
    expect(jsonTokens(undefined)).toEqual([{ text: "null", kind: "num" }]);
  });
});

describe("live card sources", () => {
  it("shows the path on the face and parameter names without values on the back", () => {
    const url = "/api/desktop-v3/node-brief?project=p1&workspace=w1&nodeId=n%201&layer=souhrn";
    expect(sourcePath(url)).toBe("/api/desktop-v3/node-brief");
    expect(sourceShape(url)).toBe("/api/desktop-v3/node-brief?project&workspace&nodeId&layer");
    expect(sourcePath("/api/pletor/linie/trace")).toBe("/api/pletor/linie/trace");
    expect(sourceShape("/api/pletor/linie/trace")).toBe("/api/pletor/linie/trace");
    expect(sourceShape("/api/x?")).toBe("/api/x");
  });
});

describe("mirrorShown", () => {
  const item = (name: string, status: "ok" | "miss" | "bad") => ({ kind: "file" as const, name, path: name, line: null, status, text: "" });
  it("dá ujetí a chybějící nahoru a zbytek schová", async () => {
    const { mirrorShown } = await import("./live-card-view");
    const items = [item("a", "ok"), item("b", "miss"), item("c", "bad"), item("d", "ok")];
    expect(mirrorShown(items, 2, false)).toEqual({ shown: [items[2], items[1]], rest: 2 });
    expect(mirrorShown(items, 2, true).rest).toBe(0);
  });
});
