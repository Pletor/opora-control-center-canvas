import { describe, expect, it } from "vitest";
import { linieFixture } from "./linie-fixture";
import { COL, HEAD, LANE_GAP, clip, layoutGraph, laneColor, laneSubtitle } from "./linie-graph";
import { graphView } from "./linie-view";
import { hueOf } from "./linie-color";

const lanes = graphView(linieFixture).lanes;
const layout = layoutGraph(lanes);
const dot = (sha: string) => layout.dots.find((item) => item.sha === sha)!;

describe("layoutGraph", () => {
  it("sloupce podle času, nejstarší vlevo, linie pod sebou po 110 px, popisky střídavě nad a pod", () => {
    expect(layout.dots.map((item) => item.sha)).toEqual(["m1", "d1", "f1", "f2", "d2", "m2"]);
    expect(dot("m1").x).toBe(HEAD + COL / 2);
    expect(dot("d1").x - dot("m1").x).toBe(COL);
    expect(layout.dots.map((item) => item.above)).toEqual([true, false, true, false, true, false]);
    expect(layout.lanes.map((lane) => lane.y)).toEqual([60, 60 + LANE_GAP, 60 + 2 * LANE_GAP]);
    expect(layout.width).toBeGreaterThanOrEqual(HEAD + 6 * COL + 40);
    expect(layout.height).toBe(60 + 2 * LANE_GAP + 60);
  });
  it("main a develop vedou celou šířkou, téma jen od prvního do posledního commitu", () => {
    const [main, , feat] = layout.lanes;
    expect([main.x1, main.x2]).toEqual([HEAD, HEAD + 6 * COL + 40 - 16]);
    expect([feat.x1, feat.x2]).toEqual([dot("f1").x, dot("f2").x]);
    expect(feat.label).toBe("Téma: detail-karty");
  });
  it("odbočení z base a návraty merge commitem", () => {
    const at = (sha: string) => ({ x: dot(sha).x, y: dot(sha).y });
    const feat = `hsl(${hueOf("feat/detail-karty")} 75% 56%)`;
    expect(layout.links).toEqual([
      { from: at("m1"), to: at("d1"), kind: "fork", color: "#60a5fa" },
      { from: at("d1"), to: at("f1"), kind: "fork", color: feat },
      { from: at("f2"), to: at("d2"), kind: "merge", color: feat },
      { from: at("d2"), to: at("m2"), kind: "merge", color: "#60a5fa" },
    ]);
  });
  it("vidlička z parent i pro hloubku 3 a barva items", () => {
    const mk = (name: string, role: string, parent: string | null, sha: string, base: string | null, at: string) =>
      ({ name, role, parent, sha, base, commits: [{ sha, sha7: sha, title: name, at, parents: base ? [base] : [] }], acceptance: null, preview: null, pr: null });
    const deep = layoutGraph([
      mk("feat/a", "feat", "develop", "a1", null, "2026-11-01T10:00:00Z"), mk("feat/a-b", "feat", "feat/a", "b1", "a1", "2026-11-02T10:00:00Z"),
      mk("feat/a-b-c", "feat", "feat/a-b", "c1", "b1", "2026-11-03T10:00:00Z"), mk("items/x", "items", "develop", "x1", null, "2026-11-04T10:00:00Z"),
    ] as never);
    const at = (sha: string) => deep.dots.find((d) => d.sha === sha)!;
    expect(deep.links.find((l) => l.to.x === at("c1").x)!.from).toEqual({ x: at("b1").x, y: at("b1").y });
    const color = (name: string) => deep.lanes.find((lane) => lane.name === name)!.color;
    expect(color("items/x")).toBe("#c084fc");
    const hue = hueOf("feat/a"); // dítě dědí odstín kořene, hlubší je bledší a světlejší
    expect([color("feat/a"), color("feat/a-b"), color("feat/a-b-c")]).toEqual([`hsl(${hue} 75% 56%)`, `hsl(${hue} 66% 64%)`, `hsl(${hue} 57% 72%)`]);
  });
  it("base mimo commity rodiče → oblouk z hlavičky rodiče", () => {
    const moved = lanes.map((lane) => (lane.name === "feat/detail-karty" ? { ...lane, base: "neznámý" } : lane));
    const fork = layoutGraph(moved).links.find((link) => link.color !== "#60a5fa" && link.kind === "fork")!;
    expect(fork.from).toEqual({ x: HEAD, y: 60 + LANE_GAP });
  });
  it("štítky u špičky: přijetí, náhled, PR, zastaralé", () => {
    expect(layout.badges.map((badge) => [badge.lane, badge.kind, badge.text])).toEqual([
      ["develop", "preview", "Náhled (ukázka v aplikaci)"],
      ["feat/detail-karty", "accepted", "PR: přijato do develop"],
      ["feat/detail-karty", "pr", "PR #7 open"],
    ]);
    const [accepted, pr] = layout.badges.slice(1);
    expect(accepted.y).toBe(dot("f2").y);
    expect(accepted.x).toBeGreaterThan(dot("f2").x);
    expect(pr.x).toBeGreaterThan(accepted.x);
    const stale = lanes.map((lane) => (lane.acceptance ? { ...lane, acceptance: { ...lane.acceptance, valid: false } } : lane));
    expect(layoutGraph(stale).badges[1]).toMatchObject({ kind: "stale", text: "přijetí zastaralé (f2bbbbb)" });
  });
  it("barvy, podtitulky, zkrácení a prázdný graf", () => {
    const fixed = ["main", "develop", "hotfix/1", "experiment/v"].map((name) => laneColor({ name }, []));
    expect(fixed).toEqual(["#4ade80", "#60a5fa", "#f87171", "#a39cc4"]);
    expect(laneSubtitle({ name: "main", role: "main" })).toBe("Stabilní přijaté vydání");
    expect(laneSubtitle({ name: "develop", role: "develop" })).toBe("Společné ověření");
    expect(clip("x".repeat(60))).toHaveLength(20);
    expect(layoutGraph([])).toMatchObject({ dots: [], links: [], badges: [], height: 120 });
  });
});
