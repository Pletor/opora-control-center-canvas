// Čistý model Schránky v levém menu Editoru (návrh Claude Design „Main“ a docs/navrh-schranka-zadani.md
// „Levé menu“, docs/schranka-neurony.md §6): sekce vnitřního menu, počty, hledání, výzkum s verdiktem, otázky K upřesnění,
// přehled „čeká na tebe“, rozsah a vlastník schránky. Bez Reactu; data přicházejí ze stromu GET /api/brief-vault.
import { coverageOf, type Coverage, type Feedback, type Verdict, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";

export type SectionId = "overview" | "tree" | "mvp" | "research" | "questions" | "feedback" | "decisions" | "materials" | "ideas" | "history";
export type SectionDef = { id: SectionId; label: string; title: string; icon: string };

// Ikony: tahy 24×24 z návrhu (stroke, bez výplně), aby menu mluvilo stejným jazykem jako artboard Main.
export const SECTION_GROUPS: { label: string; items: SectionDef[] }[] = [
  { label: "Plán", items: [
    { id: "overview", label: "Přehled", title: "Přehled plánu", icon: "M4 5h16v14H4zM4 10h16M10 10v9" },
    { id: "tree", label: "Zadání", title: "Zadání", icon: "M5 6h14M5 12h10M9 18h10M5 12v6h4" },
    { id: "mvp", label: "MVP a distribuce", title: "MVP a distribuce", icon: "M12 3l7 4v10l-7 4-7-4V7zM12 12l7-5M12 12v9M12 12L5 7" },
  ] },
  { label: "Vývoj", items: [
    { id: "research", label: "Výzkum", title: "Výzkum a ověřování", icon: "M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3" },
    { id: "questions", label: "K upřesnění", title: "K upřesnění", icon: "M9.5 9a2.5 2.5 0 115 .5c0 1.5-2.5 2-2.5 3.5M12 17h.01M12 21a9 9 0 100-18 9 9 0 000 18z" },
    { id: "feedback", label: "Zpětná vazba", title: "Zpětná vazba", icon: "M4 5h16v11H9l-5 4z" },
  ] },
  { label: "Know-how", items: [
    { id: "decisions", label: "Rozhodnutí", title: "Rozhodnutí", icon: "M12 3v18M5 7h14M5 7l-2 6h4zM19 7l-2 6h4z" },
    { id: "materials", label: "Podklady", title: "Podklady", icon: "M8 12l6-6a3 3 0 114 4l-8 8a5 5 0 01-7-7l7-7" },
    { id: "ideas", label: "Podněty", title: "Podněty", icon: "M9 18h6M10 21h4M12 3a6 6 0 00-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0012 3z" },
  ] },
  { label: "Historie", items: [
    { id: "history", label: "Revize", title: "Revize", icon: "M3 12a9 9 0 103-6.7L3 8M3 3v5h5M12 7v5l3 2" },
  ] },
];
export const SECTIONS: SectionDef[] = SECTION_GROUPS.flatMap((group) => group.items);

export const VERDICTS: Record<Verdict, { label: string; tone: "ok" | "gold" | "danger" | "muted" }> = {
  feasible: { label: "reálné", tone: "ok" },
  dead_end: { label: "slepá ulička", tone: "gold" },
  unrealistic: { label: "nereálné", tone: "danger" },
  unverified: { label: "neověřeno", tone: "muted" },
};
export const RESEARCH_STATUS = { assigned: "zadáno", running: "běží", done: "hotovo" } as const;
export const CONFIDENCE = { "": "—", low: "nízká", medium: "střední", high: "vysoká" } as const;

export type Flat = { node: VaultNode; depth: number; path: string[]; parent: VaultNode | null };

/** Strom do plochého seznamu v pořadí čtení, bez rekurze (server hloubku stejně omezuje). */
export function flatten(roots: VaultNode[]): Flat[] {
  const result: Flat[] = [];
  const stack: Flat[] = roots.slice().reverse().map((node) => ({ node, depth: 0, path: [], parent: null }));
  while (stack.length) {
    const item = stack.pop()!;
    result.push(item);
    const path = [...item.path, item.node.title];
    for (let index = item.node.children.length - 1; index >= 0; index--)
      stack.push({ node: item.node.children[index], depth: item.depth + 1, path, parent: item.node });
  }
  return result;
}

/** Hledání bez ohledu na velikost písmen a diakritiku („uloziste“ najde „Úložiště“). */
export function fold(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase("cs");
}

export function matches(node: VaultNode, query: string): boolean {
  const needle = fold(query.trim());
  if (!needle) return true;
  return fold([node.title, node.research?.question ?? "", node.note].join(" ")).includes(needle);
}

/** Strom zúžený na shody hledání: shoda ukáže i své předky (cestu), ostatní větve zmizí. */
export function filterTree(roots: VaultNode[], query: string): VaultNode[] {
  if (!query.trim()) return roots;
  const keep = (node: VaultNode): VaultNode | null => {
    const children = node.children.map(keep).filter((child): child is VaultNode => !!child);
    return matches(node, query) || children.length ? { ...node, children } : null;
  };
  return roots.map(keep).filter((node): node is VaultNode => !!node);
}

export function researchItems(roots: VaultNode[], query = ""): Flat[] {
  return flatten(roots).filter((item) => item.node.kind === "research" && matches(item.node, query));
}

export function questionItems(roots: VaultNode[], query = ""): Flat[] {
  return flatten(roots).filter((item) => item.node.kind === "question" && matches(item.node, query));
}

export type VerdictCounts = Record<Verdict, number>;
export function verdictCounts(roots: VaultNode[]): VerdictCounts {
  const counts: VerdictCounts = { feasible: 0, dead_end: 0, unrealistic: 0, unverified: 0 };
  researchItems(roots).forEach((item) => { counts[item.node.research?.verdict ?? "unverified"] += 1; });
  return counts;
}

export type WaitingItem = { id: string; text: string; section: SectionId; action: string; tone: "research" | "proposed" | "mvp" | "changed" };

/** „Čeká na tebe“: hotový výzkum bez zpětné vazby, otázky pro člověka, návrhy MVP a změněné zadání karet. */
export function waitingOnHuman(roots: VaultNode[], feedback: Feedback[] = []): WaitingItem[] {
  const answered = new Set(feedback.map((item) => item.fragmentId));
  const list = flatten(roots).map((item) => item.node).filter((node) => !node.offPath);
  const items: WaitingItem[] = [];
  list.filter((node) => node.kind === "research" && node.research?.status === "done" && !answered.has(node.id))
    .forEach((node) => items.push({ id: "r:" + node.id, text: `Výzkum „${node.title}“ čeká na tvou zpětnou vazbu`, section: "research", action: "Otevřít", tone: "research" }));
  list.filter((node) => node.kind === "question" && node.question?.askedFor === "human" && !node.question.answered)
    .forEach((node) => items.push({ id: "q:" + node.id, text: `Otázka: ${node.title}`, section: "questions", action: "Odpovědět", tone: "proposed" }));
  const proposed = list.filter((node) => node.kind === "brief" && node.mvp === "proposed").length;
  if (proposed) items.push({ id: "mvp", text: `${proposed} ${czCount(proposed, "fragment navržený", "fragmenty navržené", "fragmentů navržených")} do MVP čeká na potvrzení`, section: "mvp", action: "Potvrdit", tone: "mvp" });
  const changed = list.filter((node) => node.changedSinceInsert).length;
  if (changed) items.push({ id: "changed", text: `${changed} ${czCount(changed, "fragment se změnil", "fragmenty se změnily", "fragmentů se změnilo")} po vložení do karty`, section: "tree", action: "Ukázat", tone: "changed" });
  return items;
}

export type SectionCounts = Partial<Record<SectionId, number>>;
export function sectionCounts(roots: VaultNode[], extra: { feedback: number; decisions: number; materials: number; ideas: number }): SectionCounts {
  const coverage: Coverage = coverageOf(roots);
  return {
    tree: coverage.leaves,
    research: researchItems(roots).length,
    questions: questionItems(roots).filter((item) => !item.node.question?.answered).length,
    feedback: extra.feedback, decisions: extra.decisions, materials: extra.materials, ideas: extra.ideas,
  };
}

/** Česká množná čísla: 1 kapitola, 2–4 kapitoly, 5+ kapitol. */
export function czCount(n: number, one: string, few: string, many: string): string {
  return n === 1 ? one : n >= 2 && n <= 4 ? few : many;
}

/** Krátký čas „9. 10. 21:10“. */
export function shortWhen(at: string): string {
  const date = new Date(at);
  return Number.isNaN(date.getTime()) ? at : date.toLocaleString("cs-CZ", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Hostitel URL důkazu pro řádek „postgresql.org · ověřeno 9. 10.“; neplatná adresa = prázdno. */
export function hostOf(url: string): string {
  try { return new URL(url).host.replace(/^www\./, ""); } catch { return ""; }
}

/** Odkaz ven jen pro http(s); cokoli jiného (javascript:, data:) se vykreslí jako text. */
export function safeHref(url: string): string | undefined {
  try { const parsed = new URL(url); return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : undefined; }
  catch { return undefined; }
}

type ScopeNode = { id: string; name: string; kind: string; parentId: string | null };

/** Uzly v rozsahu schránky: vlastník a všichni jeho potomci (plátno = všechny). */
export function scopeIds(scope: string, nodes: Omit<ScopeNode, "name">[]): Set<string> {
  if (!scope) return new Set(nodes.map((node) => node.id));
  const ids = new Set([scope]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const node of nodes) if (node.parentId && ids.has(node.parentId) && !ids.has(node.id)) { ids.add(node.id); grew = true; }
  }
  return ids;
}

/** Vlastník schránky do věty „Schránka sektoru „3. VRSTVA““: plátno, sektor, karta, nebo neznámá vrstva. */
export function ownerLabel(scope: string, nodes: ScopeNode[]): string {
  if (!scope) return "plátna";
  const owner = nodes.find((node) => node.id === scope);
  return owner ? `${owner.kind === "sector" ? "sektoru" : "karty"} „${owner.name}“` : "vrstvy";
}
