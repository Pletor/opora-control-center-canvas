import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import BriefVaultDock from "./BriefVaultDock";
import TrackSwitch from "./TrackSwitch";
import TrackReassign from "./TrackReassign";
import RootCreateForm from "./RootCreateForm";
import VaultNav from "./VaultNav";
import OverviewSection from "./OverviewSection";
import MvpSection from "./MvpSection";
import ResearchSection from "./ResearchSection";
import QuestionsSection from "./QuestionsSection";
import FeedbackSection from "./FeedbackSection";
import { DecisionsSection, IdeasSection, MaterialsSection } from "./KnowHowSections";
import IdeasPanel from "@/editor/node-detail/ideas/components/IdeasPanel";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "w" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
});
const scope = { project: "p", workspace: "w" };
// Komponenty s povinnými props renderujeme staticky (bez DOM).
const render = (type: unknown, props: object) => renderToStaticMarkup(createElement(type as never, props as never));

describe("brief vault dock", () => {
  it("is a panel (not a modal) with the track switch, the inner menu and search", () => {
    const html = render(BriefVaultDock, { project: "p", workspace: "w", scope: "s", owner: "sektoru „3. VRSTVA“", focus: null,
      state: emptyDesktopState(), nodes: [], digest: "d", readOnly: false, onOpenNode: () => {},
      onPlanApplied: () => {}, onStateChanged: () => {} });
    expect(html).not.toContain("<dialog");
    expect(html).not.toContain("Zavřít schránku");
    expect(html).toContain('data-testid="brief-vault-dock"');
    expect(html).toContain('aria-label="Hledat ve schránce"');
    for (const label of ["CX/UX/UI", "Backend + DB", "Nezařazené", "Plán", "Vývoj", "Know-how", "Historie", "Přehled", "Zadání",
      "MVP a distribuce", "Výzkum", "K upřesnění", "Zpětná vazba", "Rozhodnutí", "Podklady", "Podněty", "Revize"]) expect(html).toContain(label);
    expect(html).toContain("Schránka sektoru „3. VRSTVA“");
  });

  it("track switch marks the chosen track and shows counts", () => {
    const html = render(TrackSwitch, { track: "logic", counts: { ux: 4, logic: 7, none: 0 }, onTrack: () => {} });
    expect(html).toMatch(/aria-pressed="true"[^>]*data-testid="vault-track-logic"[^>]*>Backend \+ DB<span[^>]*>7</);
    expect(html).toContain('data-testid="vault-track-ux"');
  });

  it("fragment detail shows its track and offers to move it", () => {
    const own = node("Výpočet", { parentId: "r", track: "logic", effectiveTrack: "logic" });
    const html = render(TrackReassign, { scope, fragment: own, readOnly: false, onMoved: () => {} });
    expect(html).toContain("Stopa: Backend + DB · vlastní");
    expect(html).toContain("Přeřadit do stopy");
    expect(html).toContain("dědit po předkovi");
    const inherited = render(TrackReassign, { scope, fragment: node("Tok", { parentId: "r", track: null, effectiveTrack: "ux" }), readOnly: true, onMoved: () => {} });
    expect(inherited).toContain("Stopa: CX/UX/UI · zděděná");
    expect(inherited).not.toContain("Přeřadit");
  });

  it("a new root starts collapsed behind one button", () => {
    expect(render(RootCreateForm, { scope, vaultScope: "", track: "none", onCreated: () => {} })).toContain("Nové zadání");
  });

  it("marks the current section and shows counts in the menu", () => {
    const html = render(VaultNav, { section: "research", counts: { research: 4, tree: 60 }, query: "", owner: "plátna", onSection: () => {}, onQuery: () => {} });
    expect(html).toMatch(/aria-current="page"[^>]*>.*Výzkum.*4/s);
    expect(html).toContain(">60<");
  });

  it("overview tells the story and lists what waits on the human", () => {
    const research = node("Atomické přepnutí", { kind: "research", research: { question: "Jde to?", verdict: "feasible", confidence: "medium", status: "done", round: 1, evidence: 2 } });
    const roots = [node("Vrstva", { children: [node("3.1", { status: "inserted", inserted: true, cards: [{ nodeId: "c", revision: 1 }] }), node("3.2"), research] })];
    const html = render(OverviewSection, { roots, feedback: [], onSection: () => {} });
    expect(html).toContain("2 kapitoly zadání · 1 už pracuje jako karty");
    expect(html).toContain("1 reálné");
    expect(html).toContain("Výzkum „Atomické přepnutí“ čeká na tvou zpětnou vazbu");
  });

  it("MVP section offers insert and distribute with counts, write only after preview", () => {
    const roots = [node("Vrstva", { children: [node("3.1", { mvp: "yes" }), node("3.2", { mvp: "proposed" }), node("3.3", { inserted: true, status: "inserted" })] })];
    const html = render(MvpSection, { scope, roots, query: "", readOnly: false, digest: "d", parent: "s", onApplied: () => {} });
    expect(html).toContain("Zobrazit náhled a vložit (1)");
    expect(html).toContain("Připravit návrh (2)");
    expect(html).toContain("navrženo agentem");
    expect(html).toContain("MVP potvrzeno");
  });

  it("research list shows verdict dots and every section has an empty state", () => {
    const research = node("R", { kind: "research", research: { question: "Neo4j?", verdict: "dead_end", confidence: "high", status: "done", round: 1, evidence: 1 } });
    const roots = [node("Vrstva", { children: [research] })];
    const html = render(ResearchSection, { scope, roots, query: "", feedback: [], readOnly: false });
    expect(html).toContain("slepá ulička");
    expect(html).toContain("Neo4j?");
    expect(render(ResearchSection, { scope, roots: [node("V")], query: "", feedback: [], readOnly: false })).toContain("Zatím žádný výzkum.");
    expect(render(QuestionsSection, { scope, roots: [node("V")], query: "", readOnly: false })).toContain("Žádné otázky k upřesnění.");
    expect(render(FeedbackSection, { roots: [], feedback: [], query: "" })).toContain("Zatím žádná zpětná vazba.");
    expect(render(MaterialsSection, { materials: [], nodeNames: {}, query: "" })).toContain("Žádné podklady.");
    expect(render(DecisionsSection, { scope, roots: [], decisions: [], inScope: new Set(), nodeNames: {}, query: "", readOnly: false }))
      .toContain("Žádný fragment zatím neodkazuje na rozhodnutí.");
    expect(render(IdeasSection, { scope, roots: [], ideas: [], nodeNames: {}, vaultScope: "", track: "ux", query: "", readOnly: false, onLinked: () => {} }))
      .toContain("Žádné Podněty v rozsahu schránky.");
  });

  it("idea and fragment link both ways: chip in the vault and in the Podněty tab", () => {
    const fragment = node("3.41 Retrieval Cache");
    const idea = { id: "i1", text: "Mazat cache i při změně URL.", by: "review", source: "review", at: "", status: "open" as const, fragmentId: fragment.id };
    const vaultHtml = render(IdeasSection, { scope, roots: [node("V", { children: [fragment] })], ideas: [{ nodeId: "c", idea }, { nodeId: "c", idea: { ...idea, id: "i2", fragmentId: undefined } }],
      nodeNames: { c: "3.4 Cache" }, vaultScope: "s", track: "none", query: "", readOnly: false, onLinked: () => {} });
    expect(vaultHtml).toContain("3.41 Retrieval Cache");
    expect(vaultHtml).toContain("Udělat z toho fragment");
    const tabHtml = render(IdeasPanel, { ideas: [idea], readOnly: false, busy: false, onStatus: () => {}, onRemove: () => {},
      fragmentTitles: { [fragment.id]: fragment.title }, onOpenFragment: () => {} });
    expect(tabHtml).toContain("Ze schránky: 3.41 Retrieval Cache");
  });
});
