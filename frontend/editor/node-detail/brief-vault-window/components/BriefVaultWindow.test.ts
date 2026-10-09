import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import BriefVaultWindow, { closeOnEscape } from "./BriefVaultWindow";
import VaultNav from "./VaultNav";
import OverviewSection from "./OverviewSection";
import MvpSection from "./MvpSection";
import ResearchSection from "./ResearchSection";
import QuestionsSection from "./QuestionsSection";
import FeedbackSection from "./FeedbackSection";
import { DecisionsSection, IdeasSection, MaterialsSection } from "./KnowHowSections";
import BriefVaultEntry from "@/editor/node-detail/brief-vault/components/BriefVaultEntry";
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

describe("brief vault window", () => {
  it("is a modal dialog with the left menu, search and a close button", () => {
    const html = render(BriefVaultWindow, { project: "p", workspace: "w", request: { scope: "s", owner: "sektoru „3. VRSTVA“" },
      state: emptyDesktopState(), nodes: [], digest: "d", readOnly: false, onOpenNode: () => {}, onClose: () => {},
      onPlanApplied: () => {}, onStateChanged: () => {} });
    expect(html).toContain("<dialog");
    expect(html).toContain('aria-label="Zavřít schránku"');
    expect(html).toContain('aria-label="Hledat ve schránce"');
    for (const label of ["Plán", "Vývoj", "Know-how", "Historie", "Přehled", "Zadání", "MVP a distribuce", "Výzkum", "K upřesnění",
      "Zpětná vazba", "Rozhodnutí", "Podklady", "Podněty", "Revize"]) expect(html).toContain(label);
    expect(html).toContain("Schránka sektoru „3. VRSTVA“");
  });

  it("closes on Escape and on the native cancel event, nothing else", () => {
    const onClose = vi.fn();
    const event = (type: string, key?: string) => ({ type, key, preventDefault: vi.fn(), stopPropagation: vi.fn() });
    const esc = event("keydown", "Escape");
    closeOnEscape(esc, onClose);
    closeOnEscape(event("cancel"), onClose);
    closeOnEscape(event("keydown", "Enter"), onClose);
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(esc.preventDefault).toHaveBeenCalled();
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
    expect(render(IdeasSection, { scope, roots: [], ideas: [], nodeNames: {}, vaultScope: "", query: "", readOnly: false, onLinked: () => {} }))
      .toContain("Žádné Podněty v rozsahu schránky.");
  });

  it("idea and fragment link both ways: chip in the vault and in the Podněty tab", () => {
    const fragment = node("3.41 Retrieval Cache");
    const idea = { id: "i1", text: "Mazat cache i při změně URL.", by: "review", source: "review", at: "", status: "open" as const, fragmentId: fragment.id };
    const vaultHtml = render(IdeasSection, { scope, roots: [node("V", { children: [fragment] })], ideas: [{ nodeId: "c", idea }, { nodeId: "c", idea: { ...idea, id: "i2", fragmentId: undefined } }],
      nodeNames: { c: "3.4 Cache" }, vaultScope: "s", query: "", readOnly: false, onLinked: () => {} });
    expect(vaultHtml).toContain("3.41 Retrieval Cache");
    expect(vaultHtml).toContain("Udělat z toho fragment");
    const tabHtml = render(IdeasPanel, { ideas: [idea], readOnly: false, busy: false, onStatus: () => {}, onRemove: () => {},
      fragmentTitles: { [fragment.id]: fragment.title }, onOpenFragment: () => {} });
    expect(tabHtml).toContain("Ze schránky: 3.41 Retrieval Cache");
  });

  it("entry from a card or sector is a bar, a summary and the open button", () => {
    const roots = [node("V", { children: [node("3.1", { status: "changed", changedSinceInsert: true, cards: [{ nodeId: "c", revision: 1 }] }), node("3.2")] })];
    const html = render(BriefVaultEntry, { roots, loading: false, error: "", readOnly: false, onOpen: () => {} });
    expect(html).toContain("Otevřít schránku");
    expect(html).toContain("2 kapitoly · 1 jako karty · 0 výzkumů · 0 k upřesnění");
    expect(html).toContain("⚠ 1 změněno po vložení");
  });
});
