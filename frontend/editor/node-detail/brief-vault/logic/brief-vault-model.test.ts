import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  briefChips, countChangedMvp, scopeOfFragment, coverageKey, coverageOf, coverageSegments, hasOwnVault, indexVault, rootsOf, statusDot,
  type VaultNode,
} from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import BriefVaultPanel from "@/editor/node-detail/brief-vault/components/BriefVaultPanel";
import BriefChips from "@/editor/node-detail/brief-vault/components/BriefChips";

let seq = 0;
const node = (extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "f" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: seq, kind: "brief", title: "Kapitola " + seq,
  stage: "draft", mvp: "none", note: "", by: "agent", actor: "agent", at: "2026-10-09T10:00:00+00:00", deleted: false,
  chars: 10, status: "saved", inserted: false, cards: [], changedSinceInsert: false, ideas: 0, children: [], ...extra,
});

describe("coverage from the tree", () => {
  it("counts brief leaves once each and ignores research children and inner nodes", () => {
    const research = node({ kind: "research", stage: "research", status: "research" });
    const root = node({ scopeNodeId: "sector", children: [
      node({ status: "inserted", mvp: "yes", inserted: true, cards: [{ nodeId: "c1", revision: 1 }] }),
      node({ status: "inserted", inserted: true, cards: [{ nodeId: "c2", revision: 1 }] }),
      node({ status: "changed", revision: 2, mvp: "yes", cards: [{ nodeId: "c3", revision: 1 }], changedSinceInsert: true }),
      node({ status: "research", children: [research] }),
      node({ status: "mvp", mvp: "yes" }),
      node({ status: "proposed", mvp: "proposed" }),
      node(),
    ] });
    expect(coverageOf([root])).toEqual({ leaves: 7, mvpInserted: 1, inserted: 1, research: 1, saved: 3, changed: 1 });
  });

  it("treats a root without brief children as one leaf and an empty tree as zero", () => {
    expect(coverageOf([node()])).toMatchObject({ leaves: 1, saved: 1 });
    expect(coverageOf([])).toMatchObject({ leaves: 0 });
    expect(coverageSegments(coverageOf([]))).toEqual([]);
  });

  it("builds segment widths that sum to 100 % and skips empty segments", () => {
    const segments = coverageSegments(coverageOf([node({ status: "inserted" }), node(), node(), node({ status: "changed" })]));
    expect(segments.map((s) => s.key)).toEqual(["inserted", "saved", "changed"]);
    expect(segments.reduce((sum, s) => sum + s.percent, 0)).toBeCloseTo(100);
  });

  it("puts changed before the MVP flag so a changed MVP card is a warning", () => {
    expect(coverageKey({ status: "changed", mvp: "yes" })).toBe("changed");
    expect(coverageKey({ status: "inserted", mvp: "yes" })).toBe("mvpInserted");
  });
});

describe("status dots", () => {
  it("maps derived states to the port dot language", () => {
    expect(statusDot(node({ status: "inserted", mvp: "yes" })).tone).toBe("mvp");
    expect(statusDot(node({ status: "inserted" })).tone).toBe("inserted");
    expect(statusDot(node({ status: "changed" }))).toEqual({ tone: "changed", label: "změněno po vložení" });
    expect(statusDot(node({ status: "research" })).tone).toBe("research");
    expect(statusDot(node({ status: "proposed" })).label).toBe("návrh do MVP");
    expect(statusDot(node()).label).toBe("uloženo");
    expect(statusDot(node({ kind: "research", stage: "ready" })).label).toBe("research uzavřen");
  });
});

describe("changed since insert", () => {
  const latest = node({ revision: 3, title: "3.37 Version activation" });
  const same = node({ revision: 1, title: "3.36 Chunks" });
  const index = indexVault([node({ children: [latest, same] })]);

  it("flags refs planned from an older revision", () => {
    expect(briefChips([{ fragmentId: latest.id, revision: 1 }, { fragmentId: same.id, revision: 1 }], index).map((chip) => chip.changed)).toEqual([true, false]);
    expect(briefChips([{ fragmentId: latest.id, revision: 3 }], index)[0].changed).toBe(false);
    expect(briefChips(undefined, index)).toEqual([]);
  });

  it("keeps unknown fragments as unavailable chips without a warning", () => {
    expect(briefChips([{ fragmentId: "gone", revision: 2 }], index))
      .toEqual([{ fragmentId: "gone", title: "nedostupné", insertedRevision: 2, latestRevision: null, changed: false }]);
  });

  it("renders chips with the inserted revision and a warning", () => {
    const html = renderToStaticMarkup(createElement(BriefChips, { refs: [{ fragmentId: latest.id, revision: 1 }, { fragmentId: same.id, revision: 1 }], index }));
    expect(html).toContain("Ze schránky:");
    expect(html).toContain("3.37 Version activation v1 → v3 ⚠");
    expect(html).toContain("3.36 Chunks");
    expect(renderToStaticMarkup(createElement(BriefChips, { refs: [], index }))).toBe("");
  });
});

describe("text revision and MVP under a warning", () => {
  it("ignores metadata-only revisions (propose-mvp, stage) when the server sends textRevision", () => {
    const meta = node({ revision: 4, textRevision: 1, title: "3.12 Chunks", mvp: "proposed" });
    const text = node({ revision: 4, textRevision: 3, title: "3.13 Overlap" });
    const index = indexVault([node({ children: [meta, text] })]);
    expect(briefChips([{ fragmentId: meta.id, revision: 1 }], index)[0].changed).toBe(false);
    expect(briefChips([{ fragmentId: text.id, revision: 2 }], index)[0].changed).toBe(true);
    expect(briefChips([{ fragmentId: text.id, revision: 2 }], index)[0].latestRevision).toBe(3);
  });

  it("keeps MVP visible on a changed fragment (label and coverage note)", () => {
    expect(statusDot(node({ status: "changed", mvp: "yes" })).label).toBe("MVP vloženo · změněno po vložení");
    expect(statusDot(node({ status: "changed", mvp: "proposed" })).label).toBe("návrh MVP · změněno po vložení");
    const roots = [node({ children: [node({ status: "changed", mvp: "yes" }), node({ status: "changed" }), node({ status: "mvp", mvp: "yes" })] })];
    expect(countChangedMvp(roots)).toBe(1);
  });

  it("finds the vault scope of a fragment through its parents", () => {
    const leaf = node({ title: "leaf" });
    const root = node({ scopeNodeId: "sector", children: [leaf] });
    leaf.parentId = root.id;
    const index = indexVault([root]);
    expect(scopeOfFragment(index, leaf.id)).toBe("sector");
    expect(scopeOfFragment(index, "missing")).toBeNull();
  });
});

describe("scopes", () => {
  it("selects roots of a scope and detects a card with its own vault", () => {
    const canvas = node({ scopeNodeId: "" });
    const card = node({ scopeNodeId: "card" });
    expect(rootsOf([canvas, card], "")).toEqual([canvas]);
    expect(hasOwnVault([canvas, card], "card")).toBe(true);
    expect(hasOwnVault([canvas], "card")).toBe(false);
    expect(hasOwnVault([canvas, node({ scopeNodeId: "card", kind: "duel" as never }), node({ scopeNodeId: "card", kind: "vision" as never })], "card")).toBe(false);
  });
});

describe("vault panel", () => {
  const props = { project: "p", workspace: "w", loading: false, readOnly: false, error: "", scopeLabel: "sektoru", nodeNames: {}, onOpenNode: () => {} };

  it("explains an empty vault", () => {
    const html = renderToStaticMarkup(createElement(BriefVaultPanel, { ...props, roots: [] }));
    expect(html).toContain("Schránka sektoru je prázdná.");
  });

  it("draws the coverage bar with counts and a tree row per root", () => {
    const html = renderToStaticMarkup(createElement(BriefVaultPanel, { ...props, roots: [
      node({ title: "3.1 Architektura", status: "inserted", cards: [{ nodeId: "c", revision: 1 }] }),
      node({ title: "3.37 Version <b>activation</b>", status: "changed", revision: 2, cards: [{ nodeId: "c", revision: 1 }], changedSinceInsert: true }),
    ] }));
    expect(html).toContain("2 kapitoly:");
    expect(html).toContain("vloženo 1");
    expect(html).toContain("změněno 1");
    expect(html).toContain("⚠ v2 &gt; v1");
    expect(html).toContain("3.37 Version &lt;b&gt;activation&lt;/b&gt;");
    expect(html).not.toContain("<b>activation</b>");
  });
});
