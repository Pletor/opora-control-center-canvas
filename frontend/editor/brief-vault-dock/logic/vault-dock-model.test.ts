import { describe, expect, it } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import {
  SECTIONS, SECTION_GROUPS, filterTree, flatten, fold, ownerLabel, questionItems, researchItems, safeHref, scopeIds, sectionCounts, verdictCounts, waitingOnHuman,
} from "./vault-dock-model";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "n" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
});
const research = (title: string, verdict: "feasible" | "dead_end" | "unrealistic" | "unverified", status: "assigned" | "running" | "done" = "done") =>
  node(title, { kind: "research", stage: "research", research: { question: title + "?", verdict, confidence: "", status, round: 1, evidence: verdict === "unverified" ? 0 : 1 } });

describe("vault dock model", () => {
  it("has the menu groups of the design in order", () => {
    expect(SECTION_GROUPS.map((group) => group.label)).toEqual(["Plán", "Vývoj", "Know-how", "Historie"]);
    expect(SECTIONS.map((section) => section.label)).toEqual(["Přehled", "Zadání", "MVP a distribuce", "Výzkum", "K upřesnění",
      "Zpětná vazba", "Rozhodnutí", "Podklady", "Podněty", "Revize"]);
  });

  it("filters the tree by title ignoring case and diacritics and keeps the path", () => {
    const leaf = node("3.37 Aktivace verze");
    const root = node("3. VRSTVA — ÚLOŽIŠTĚ", { children: [node("3.1 Architektura"), node("3.3 Indexy", { children: [leaf] })] });
    expect(fold("ÚLOŽIŠTĚ")).toBe("uloziste");
    const found = filterTree([root], "aktivace");
    expect(flatten(found).map((item) => item.node.title)).toEqual(["3. VRSTVA — ÚLOŽIŠTĚ", "3.3 Indexy", "3.37 Aktivace verze"]);
    expect(filterTree([root], "uloziste")[0].children).toHaveLength(0);
    expect(filterTree([root], "  ")).toEqual([root]);
    expect(filterTree([root], "nic takového")).toEqual([]);
  });

  it("lists research with verdicts and open questions, and counts sections", () => {
    const question = node("Co je JEV?", { kind: "question", question: { askedFor: "human", answered: false } });
    const answered = node("Kanály?", { kind: "question", question: { askedFor: "human", answered: true } });
    const root = node("Vrstva", { children: [node("3.1", { children: [research("Neo4j", "dead_end"), question] }), research("Video", "unverified", "assigned"), answered] });
    expect(researchItems([root]).map((item) => item.parent?.title)).toEqual(["3.1", "Vrstva"]);
    expect(researchItems([root], "neo")).toHaveLength(1);
    expect(verdictCounts([root])).toEqual({ feasible: 0, dead_end: 1, unrealistic: 0, unverified: 1 });
    expect(questionItems([root]).map((item) => item.node.title)).toEqual(["Co je JEV?", "Kanály?"]);
    expect(sectionCounts([root], { feedback: 2, decisions: 1, materials: 0, ideas: 3 })).toEqual({
      tree: 1, research: 2, questions: 1, feedback: 2, decisions: 1, materials: 0, ideas: 3 });
  });

  it("collects what waits on the human", () => {
    const done = research("Atomické přepnutí", "feasible");
    const reviewed = research("Fulltext", "feasible");
    const question = node("Co je JEV?", { kind: "question", question: { askedFor: "human", answered: false } });
    const root = node("Vrstva", { children: [done, reviewed, question, node("3.34", { mvp: "proposed" }), node("3.12", { changedSinceInsert: true, status: "changed" })] });
    const items = waitingOnHuman([root], [{ id: "x", fragmentId: reviewed.id, fragmentRevision: 1, verdict: "agree", text: "", by: "human", actor: "human", at: "" }]);
    expect(items.map((item) => [item.section, item.text])).toEqual([
      ["research", "Výzkum „Atomické přepnutí“ čeká na tvou zpětnou vazbu"],
      ["questions", "Otázka: Co je JEV?"],
      ["mvp", "1 fragment navržený do MVP čeká na potvrzení"],
      ["tree", "1 fragment se změnil po vložení do karty"],
    ]);
  });

  it("only links http(s) evidence", () => {
    expect(safeHref("https://supabase.com/docs")).toBe("https://supabase.com/docs");
    expect(safeHref("javascript:alert(1)")).toBeUndefined();
    expect(safeHref("nesmysl")).toBeUndefined();
  });
  it("skips path-only nodes of another discipline in what waits on the human", () => {
    const root = node("Vrstva", { offPath: true, mvp: "proposed", children: [node("3.1", { mvp: "proposed" })] });
    expect(waitingOnHuman([root]).map((item) => item.text)).toEqual(["1 fragment navržený do MVP čeká na potvrzení"]);
  });

  it("knows the scope of the vault and names its owner", () => {
    const nodes = [{ id: "s", name: "3. VRSTVA", kind: "sector", parentId: null }, { id: "c", name: "3.1", kind: "node", parentId: "s" },
      { id: "x", name: "Jinde", kind: "node", parentId: null }];
    expect([...scopeIds("s", nodes)].sort()).toEqual(["c", "s"]);
    expect(scopeIds("", nodes).size).toBe(3);
    expect(ownerLabel("", nodes)).toBe("plátna");
    expect(ownerLabel("s", nodes)).toBe("sektoru „3. VRSTVA“");
    expect(ownerLabel("c", nodes)).toBe("karty „3.1“");
    expect(ownerLabel("?", nodes)).toBe("vrstvy");
  });
});
