import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { emptyDesktopState } from "@/shared/desktop-state/logic/types";
import BriefVaultDock from "./BriefVaultDock";
import DisciplineSwitch from "./DisciplineSwitch";
import DisciplineOf from "./DisciplineOf";
import PlanPreview from "./PlanPreview";
import DisciplineSelect from "./DisciplineSelect";
import FragmentGates from "../fragment-gates/components/FragmentGates";
import GateBar from "@/editor/node-detail/brief-vault/components/GateBar";
import { DISCIPLINES } from "../logic/disciplines";
import type { FragmentDetail } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
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
  it("is a panel (not a modal) with the discipline switch, the inner menu and search", () => {
    const html = render(BriefVaultDock, { project: "p", workspace: "w", scope: "s", owner: "sektoru „3. VRSTVA“", focus: null,
      state: emptyDesktopState(), nodes: [], digest: "d", readOnly: false, onOpenNode: () => {},
      onPlanApplied: () => {}, onStateChanged: () => {} });
    expect(html).not.toContain("<dialog");
    expect(html).not.toContain("Zavřít schránku");
    expect(html).toContain('data-testid="brief-vault-dock"');
    expect(html).toContain('aria-label="Hledat ve schránce"');
    for (const label of ["Kreslení", "Logika", "Provoz", "Nezařazené", "Plán", "Vývoj", "Know-how", "Historie", "Přehled", "Zadání",
      "MVP a distribuce", "Výzkum", "K upřesnění", "Zpětná vazba", "Rozhodnutí", "Podklady", "Podněty", "Revize"]) expect(html).toContain(label);
    expect(html).toContain("Schránka sektoru „3. VRSTVA“");
  });

  it("discipline switch groups live neurons with counts and keeps Nezařazené on the right", () => {
    const live = DISCIPLINES.filter((item) => ["ux", "be"].includes(item.id));
    const html = render(DisciplineSwitch, { view: "be", live, counts: { ux: 4, be: 7, none: 2 }, onView: () => {} });
    expect(html).toMatch(/aria-pressed="true"[^>]*data-testid="vault-discipline-be"[^>]*>Backend<span[^>]*>7</);
    // Rozbalená je jen skupina vybrané disciplíny; ostatní hlavičky nesou počet neuronů, spící „spí“.
    expect(html).not.toContain('data-testid="vault-discipline-ux"');
    expect(html).toMatch(/aria-expanded="false"[^>]*data-testid="vault-group-kresleni"[^>]*>Kreslení<span[^>]*>1</);
    expect(html).toMatch(/aria-expanded="true"[^>]*data-testid="vault-group-logika"/);
    expect(html).not.toContain('data-testid="vault-discipline-cache"');
    expect(html).toMatch(/disabled=""[^>]*data-testid="vault-group-provoz"[^>]*>Provoz<span[^>]*>spí</);
    expect(html).not.toContain('data-testid="vault-waiting-next"');
    expect(html).toMatch(/data-testid="vault-discipline-none"[^>]*>Nezařazené<span[^>]*>2</);
    // S čekajícími věcmi se objeví odznak na hlavičce i pilulka „Čeká na tebe“ s celkovým počtem.
    const busy = render(DisciplineSwitch, { view: "be", live, counts: { ux: 4, be: 7, none: 2 }, waiting: { ux: 2, be: 0 }, onView: () => {} });
    expect(busy).toMatch(/data-testid="vault-group-kresleni"[^>]*>Kreslení<span[^>]*>1<\/span><span class="vault-dock__waiting-badge"[^>]*>2</);
    expect(busy).toMatch(/data-testid="vault-waiting-next"[^>]*>Čeká na tebe<span[^>]*>2</);
  });

  it("fragment detail shows its discipline, own or inherited, without controls", () => {
    const own = render(DisciplineOf, { fragment: node("Výpočet", { parentId: "r", discipline: "be", effectiveDiscipline: "be" }) });
    expect(own).toContain("Disciplína: Logika · Backend · vlastní");
    expect(own).not.toContain("<select");
    const inherited = render(DisciplineOf, { fragment: node("Tok", { parentId: "r", discipline: null, effectiveDiscipline: "ux" }) });
    expect(inherited).toContain("Disciplína: Kreslení · UX (tok, obrazovky, stavy) · zděděná");
  });

  it("a new root offers a grouped discipline choice", () => {
    expect(render(DisciplineSelect, { value: "", label: "Disciplína", placeholder: "vyber…", onChange: () => {} })).toContain('<optgroup label="Provoz">');
  });

  it("a new root starts collapsed behind one button", () => {
    expect(render(RootCreateForm, { scope, vaultScope: "", view: "none", onCreated: () => {} })).toContain("Nové zadání");
  });

  it("the tree row shows eight gate dots", () => {
    const html = render(GateBar, { node: { gates: { scoped: true, weighed: false, synthesized: false, decided: false, planned: false, placed: false, verified: false, learned: false, predictionError: null }, gateStep: 1 } });
    expect(html.match(/brief-gates__dot /g)).toHaveLength(8);
    expect(html).toContain("brief-gates__dot--next");
    expect(html).toContain('title="2. Zváženo: další na řadě"');
  });

  it("fragment gates list every gate with payload, who confirmed it and the dead end reason, with nothing to click", () => {
    const entry = (payload: Record<string, unknown> | null) => ({ value: true, payload, by: "Hermes", actor: "agent", at: "", inputHash: "h", revision: 2, valid: true });
    const detail = {
      fragment: { id: "f", revision: 4, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title: "F", stage: "draft", mvp: "none", note: "", by: "", actor: "", at: "", deleted: false, chars: 1, text: "t" },
      latestRevision: 4, history: [], path: [], scopeNodeId: null, status: "saved", children: [], cards: [], ideas: [], effectiveDiscipline: "be",
      gates: { scoped: true, weighed: true, synthesized: true, decided: true, planned: false, placed: false, verified: false, learned: false, predictionError: null },
      gateStep: 4, gatesStale: false, deadEnd: true,
      gateDetail: { scoped: entry(null), weighed: entry({ benefit: "Rychlost", risk: "Cache" }), synthesized: entry({ type: "API", done: "200", prediction: { tests: "pass", criticRounds: 1, risk: "r" } }),
        decided: entry({ verdict: "no", reason: "Mimo rozsah MVP." }) },
    } as FragmentDetail;
    const html = render(FragmentGates, { scope, detail });
    expect(html).toContain("Brány cyklu · 4/8");
    expect(html).toContain("Slepá ulička (rozhodnuto: ne): Mimo rozsah MVP.");
    expect(html).toContain("přínos: Rychlost");
    expect(html).toContain("předpověď · testy: projdou");
    expect(html.match(/data-testid="gate-/g)).toHaveLength(8);
    expect(html).toContain("potvrdil agent Hermes");
    expect(html).toContain("Poučení disciplíny Backend");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<input");
  });

  it("plan preview starts by asking the server and writes nothing", () => {
    const html = render(PlanPreview, { scope, digest: "d", fragmentIds: ["a"], title: "Vložit", onApplied: () => {}, onCancel: () => {}, onOpenFragment: () => {} });
    expect(html).toContain("Skládám plán na serveru");
  });

  it("marks the current section and shows counts in the menu", () => {
    const html = render(VaultNav, { section: "research", counts: { research: 4, tree: 60 }, query: "", owner: "plátna", onSection: () => {}, onQuery: () => {} });
    expect(html).toMatch(/aria-current="page"[^>]*>.*Výzkum.*4/s);
    expect(html).toContain(">60<");
  });

  it("overview tells the story and lists what waits on the human", () => {
    const research = node("Atomické přepnutí", { kind: "research", research: { question: "Jde to?", verdict: "feasible", confidence: "medium", status: "done", round: 1, evidence: 2 } });
    const roots = [node("Vrstva", { children: [node("3.1", { status: "inserted", inserted: true, cards: [{ nodeId: "c", revision: 1 }] }), node("3.2"), research] })];
    const html = render(OverviewSection, { roots, feedback: [], stats: [], view: "none", onSection: () => {}, onView: () => {} });
    expect(html).toContain("2 kapitoly zadání · 1 už pracuje jako karty");
    expect(html).toContain("1 reálné");
    expect(html).toContain("Výzkum „Atomické přepnutí“ čeká na tvou zpětnou vazbu");
  });

  it("MVP section offers insert and distribute with counts, write only after preview", () => {
    const roots = [node("Vrstva", { children: [node("3.1", { mvp: "yes" }), node("3.2", { mvp: "proposed" }), node("3.3", { inserted: true, status: "inserted" })] })];
    const html = render(MvpSection, { scope, roots, query: "", readOnly: false, digest: "d", onApplied: () => {}, onOpenFragment: () => {} });
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
    expect(render(IdeasSection, { scope, roots: [], ideas: [], nodeNames: {}, vaultScope: "", view: "ux", query: "", readOnly: false, onLinked: () => {} }))
      .toContain("Žádné Podněty v rozsahu schránky.");
  });

  it("idea and fragment link both ways: chip in the vault and in the Podněty tab", () => {
    const fragment = node("3.41 Retrieval Cache");
    const idea = { id: "i1", text: "Mazat cache i při změně URL.", by: "review", source: "review", at: "", status: "open" as const, fragmentId: fragment.id };
    const vaultHtml = render(IdeasSection, { scope, roots: [node("V", { children: [fragment] })], ideas: [{ nodeId: "c", idea }, { nodeId: "c", idea: { ...idea, id: "i2", fragmentId: undefined } }],
      nodeNames: { c: "3.4 Cache" }, vaultScope: "s", view: "none", query: "", readOnly: false, onLinked: () => {} });
    expect(vaultHtml).toContain("3.41 Retrieval Cache");
    expect(vaultHtml).toContain("Udělat z toho fragment");
    const tabHtml = render(IdeasPanel, { ideas: [idea], readOnly: false, busy: false, onStatus: () => {}, onRemove: () => {},
      fragmentTitles: { [fragment.id]: fragment.title }, onOpenFragment: () => {} });
    expect(tabHtml).toContain("Ze schránky: 3.41 Retrieval Cache");
  });
});
