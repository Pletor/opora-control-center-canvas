import { describe, expect, it } from "vitest";
import { linieFixture } from "./linie-fixture";
import { acceptanceLabel, canAccept, diffSentence, diffView, graphView, logTail, previewLabel, roleLabel, shortSha, workLane } from "./linie-view";

describe("graphView", () => {
  it("mapuje linie, commity, přijetí a PR", () => {
    const view = graphView(linieFixture);
    expect(view.lanes.map((lane) => lane.name)).toEqual(["main", "develop", "feat/detail-karty"]);
    expect(view.lanes[0].parent).toBe("");
    expect(view.lanes[1].commits[1].parents).toEqual(["d1", "f2"]);
    expect(view.lanes[2].pr).toEqual({ number: 7, state: "open", url: "https://x/pr/7", base: "develop" });
    expect(view.active).toBe("feat/detail-karty");
  });
  it("prázdná nebo chybná odpověď nespadne", () => {
    expect(graphView(null).lanes).toEqual([]);
    const view = graphView({ lanes: { error: "git" }, deployed: { error: "chybí soubor" } });
    expect(view.lanes).toEqual([]);
    expect(view.deployed).toBeNull();
    expect(view.problem).toBe("nedostupné: git · nedostupné: chybí soubor");
  });
});

describe("štítky a výběr", () => {
  const [main, develop, feat] = graphView(linieFixture).lanes;
  it("role, sha a náhled", () => {
    expect(roleLabel("feat")).toBe("pracovní");
    expect(roleLabel("nic")).toBe("jiná");
    expect(shortSha("0123456789")).toBe("0123456");
    expect(previewLabel(develop.preview)).toBe("běží");
    expect(previewLabel(null)).toBe("bez náhledu");
  });
  it("přijetí: nepřijato, platné, zastaralé", () => {
    expect(acceptanceLabel(main)).toBe("nepřijato");
    expect(acceptanceLabel(feat)).toBe("přijato f2bbbbb do develop");
    const stale = { ...feat, sha: "f3ccccccc", acceptance: { sha: "f2bbbbbbbb", target: "develop", at: "", note: "", valid: false } };
    expect(acceptanceLabel(stale)).toBe("zastaralé (přijato f2bbbbb, teď f3ccccc)");
  });
  it("kdo smí být přijat a která větev je pracovní", () => {
    expect(canAccept(main)).toBe(false);
    expect(canAccept(develop)).toBe(false);
    expect(canAccept(feat)).toBe(true);
    const lanes = [main, develop, feat];
    expect(workLane(lanes, "", "")?.name).toBe("feat/detail-karty");
    expect(workLane(lanes, "main", "")?.name).toBe("feat/detail-karty");
    expect(workLane([main, develop], "", "")).toBeNull();
  });
  it("diff, věta a konec logu", () => {
    const diff = diffView({ commits: [{ sha7: "abc1234", title: "t" }], stat: " a | 1 +", files: 3 });
    expect(diffSentence("main", diff)).toBe("Do main by přešlo 3 souborů, 1 commitů.");
    expect(diffView(null)).toEqual({ commits: [], stat: "", files: 0 });
    expect(logTail({ build: "a\nb", server: "c" }, 2)).toBe("b\nc");
  });
});
