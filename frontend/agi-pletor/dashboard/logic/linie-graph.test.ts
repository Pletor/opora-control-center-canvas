import { describe, expect, it } from "vitest";
import { linieFixture } from "./linie-fixture";
import { HEAD, LANE_GAP, ROW, clip, layoutGraph, laneColor, laneSubtitle } from "./linie-graph";
import { graphView } from "./linie-view";

const lanes = graphView(linieFixture).lanes;
const layout = layoutGraph(lanes);
const dot = (sha: string) => layout.dots.find((item) => item.sha === sha)!;

describe("layoutGraph", () => {
  it("řádky podle času, nejstarší nahoře, linie po 150 px", () => {
    expect(layout.dots.map((item) => item.sha)).toEqual(["m1", "d1", "f1", "f2", "d2", "m2"]);
    expect(dot("m1").y).toBe(HEAD + ROW / 2);
    expect(dot("d1").y - dot("m1").y).toBe(ROW);
    expect(layout.lanes.map((lane) => lane.x)).toEqual([40, 40 + LANE_GAP, 40 + 2 * LANE_GAP]);
    expect(layout.height).toBe(HEAD + 6 * ROW + 40);
  });
  it("main a develop vedou celou výškou, téma jen od prvního do posledního commitu", () => {
    const [main, , feat] = layout.lanes;
    expect([main.top, main.bottom]).toEqual([HEAD, layout.height - 16]);
    expect([feat.top, feat.bottom]).toEqual([dot("f1").y, dot("f2").y]);
    expect(feat.label).toBe("Téma: detail-karty");
  });
  it("odbočení z base a návraty merge commitem", () => {
    const at = (sha: string) => ({ x: dot(sha).x, y: dot(sha).y });
    expect(layout.links).toEqual([
      { from: at("m1"), to: at("d1"), kind: "fork", color: "#60a5fa" },
      { from: at("d1"), to: at("f1"), kind: "fork", color: "#fb923c" },
      { from: at("f2"), to: at("d2"), kind: "merge", color: "#fb923c" },
      { from: at("d2"), to: at("m2"), kind: "merge", color: "#60a5fa" },
    ]);
  });
  it("base mimo commity rodiče → oblouk z hlavičky rodiče", () => {
    const moved = lanes.map((lane) => (lane.name === "feat/detail-karty" ? { ...lane, base: "neznámý" } : lane));
    const fork = layoutGraph(moved).links.find((link) => link.color === "#fb923c" && link.kind === "fork")!;
    expect(fork.from).toEqual({ x: 40 + LANE_GAP, y: HEAD });
  });
  it("štítky u špičky: přijetí, náhled, PR, zastaralé", () => {
    expect(layout.badges.map((badge) => [badge.lane, badge.kind, badge.text])).toEqual([
      ["develop", "preview", "Náhled (ukázka v aplikaci)"],
      ["feat/detail-karty", "accepted", "PR: přijato do develop"],
      ["feat/detail-karty", "pr", "PR #7 open"],
    ]);
    const [accepted, pr] = layout.badges.slice(1);
    expect(accepted.y).toBe(dot("f2").y + ROW / 2);
    expect(pr.x).toBeGreaterThan(accepted.x);
    const stale = lanes.map((lane) => (lane.acceptance ? { ...lane, acceptance: { ...lane.acceptance, valid: false } } : lane));
    expect(layoutGraph(stale).badges[1]).toMatchObject({ kind: "stale", text: "přijetí zastaralé (f2bbbbb)" });
  });
  it("barvy, podtitulky, zkrácení a prázdný graf", () => {
    expect([laneColor("main"), laneColor("develop"), laneColor("hotfix"), laneColor("experiment")]).toEqual(["#4ade80", "#60a5fa", "#fb923c", "#c084fc"]);
    expect(laneSubtitle({ name: "main", role: "main" })).toBe("Stabilní přijaté vydání");
    expect(laneSubtitle({ name: "develop", role: "develop" })).toBe("Společné ověření");
    expect(clip("x".repeat(60))).toHaveLength(48);
    expect(layoutGraph([])).toMatchObject({ dots: [], links: [], badges: [], height: HEAD + 40 });
  });
});
