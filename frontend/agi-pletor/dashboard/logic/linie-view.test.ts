import { describe, expect, it } from "vitest";
import { acceptanceLabel, acceptanceTone, canAccept, diffSentence, diffView, linieView, previewLabel, roleLabel, shortSha, targetOf } from "./linie-view";

const raw = {
  main: { sha: "aaaaaaa111", remote: "aaaaaaa111" },
  develop: null,
  server: { branch: "feat/x", sha: "bbbbbbb222", dirty: true },
  deployed: { error: "chybí soubor" },
  branches: [
    { name: "main", role: "main", parent: "", sha: "aaaaaaa111", ahead: 0, behind: 0, acceptance: null, preview: null },
    { name: "feat/x", role: "feat", parent: "main", sha: "bbbbbbb222", ahead: 2, behind: 1, acceptance: { sha: "ccccccc333", target: "main", valid: false }, preview: { slug: "feat-x", state: "running", url: "http://127.0.0.1:9001" } },
  ],
  enforcement: "nevynuceno",
};

describe("linieView", () => {
  it("mapuje sekce, větve a hlásí {error}", () => {
    const view = linieView(raw);
    expect(view.develop).toBeNull();
    expect(view.deployed).toBeNull();
    expect(view.server).toEqual({ branch: "feat/x", sha: "bbbbbbb222", dirty: true });
    expect(view.problem).toBe("nedostupné: chybí soubor");
    expect(view.branches[1]).toMatchObject({ ahead: 2, behind: 1, preview: { state: "running" } });
  });
  it("prázdná nebo chybná odpověď nespadne", () => {
    expect(linieView(null).branches).toEqual([]);
    const view = linieView({ branches: { error: "git" } });
    expect(view.branches).toEqual([]);
    expect(view.problem).toBe("nedostupné: git");
  });
});

describe("štítky", () => {
  const [main, feat] = linieView(raw).branches;
  it("role, sha a náhled", () => {
    expect(roleLabel("feat")).toBe("pracovní");
    expect(roleLabel("nic")).toBe("jiná");
    expect(shortSha("0123456789")).toBe("0123456");
    expect(previewLabel(feat.preview)).toBe("běží");
    expect(previewLabel({ slug: "", state: "building", url: "", sha: "" })).toBe("sestavuje se…");
    expect(previewLabel(null)).toBe("bez náhledu");
  });
  it("přijetí: nepřijato, zastaralé, platné", () => {
    expect(acceptanceLabel(main)).toBe("nepřijato");
    expect(acceptanceTone(main)).toBe("none");
    expect(acceptanceLabel(feat)).toBe("zastaralé (přijato ccccccc, teď bbbbbbb)");
    expect(acceptanceTone(feat)).toBe("stale");
    const fresh = { ...feat, acceptance: { sha: feat.sha, target: "main", at: "", note: "", valid: true } };
    expect(acceptanceLabel(fresh)).toBe("přijato bbbbbbb do main");
    expect(acceptanceTone(fresh)).toBe("ok");
  });
  it("kdo smí být přijat a kam", () => {
    expect(canAccept(main)).toBe(false);
    expect(canAccept(feat)).toBe(true);
    expect(canAccept({ ...feat, sha: "" })).toBe(false);
    expect(targetOf(feat)).toBe("main");
  });
  it("diff a věta", () => {
    const diff = diffView({ commits: [{ sha7: "abc1234", title: "t" }], stat: " a | 1 +", files: 3 });
    expect(diffSentence("main", diff)).toBe("Do main by přešlo 3 souborů, 1 commitů.");
    expect(diffView(null)).toEqual({ commits: [], stat: "", files: 0 });
  });
});
