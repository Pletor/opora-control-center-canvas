// Z fragmentů schránky koncept dávky /api/canvas-plan (návrh „Výběr MVP → karty“ a „Rozdistribuovat zbytek
// plánu“). Každá karta nese `fragmentRef` na svůj fragment i podfragmenty, podfragmenty jsou bloky karty.
// Text zadání se do karty nekopíruje: agent ho dostane doslovně v node-brief.fragments. Zápis potvrzuje člověk
// po `dryRun` náhledu; tady se dávka jen skládá.
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { textRevisionOf } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { flatten } from "./vault-window-model";

export const MAX_PLAN_CARDS = 200;
const MAX_REFS = 50;
const MAX_BLOCKS = 40;

export type PlanCard = {
  ref: string;
  kind: "node";
  parent: string | null;
  name: string;
  purpose: string;
  text: string;
  card: { status: "draft" };
  fragmentRef: { fragmentId: string }[];
  blocks: { ref: string; title: string; text: string; condition: string }[];
};
export type VaultPlan = { cards: PlanCard[]; skipped: number; fragments: VaultNode[] };

const clip = (text: string, limit: number) => (text.length > limit ? text.slice(0, limit - 1).trimEnd() + "…" : text);
const briefs = (node: VaultNode) => node.children.filter((child) => child.kind === "brief");

function hasInserted(node: VaultNode): boolean {
  return flatten([node]).some((item) => item.node.kind === "brief" && item.node.inserted);
}

/**
 * „Rozdistribuovat zbytek plánu“: nevložené části zadání → kandidáti na karty. Větev bez jediné karty
 * je jedna karta (její podfragmenty = bloky); větev, kde už něco vloženo je, se dělí na své děti.
 * Kořen schránky je celé zadání, takže kartou se stává až jeho dítě (kořen bez dětí výjimkou).
 */
export function distributeCandidates(roots: VaultNode[]): VaultNode[] {
  const result: VaultNode[] = [];
  const stack: { node: VaultNode; root: boolean }[] = roots.slice().reverse().map((node) => ({ node, root: true }));
  while (stack.length) {
    const { node, root } = stack.pop()!;
    if (node.kind !== "brief" || node.inserted) continue;
    const kids = briefs(node);
    if (!kids.length || (!root && !hasInserted(node))) { result.push(node); continue; }
    for (let index = kids.length - 1; index >= 0; index--) stack.push({ node: kids[index], root: false });
  }
  return result;
}

/** „Vložit vybrané jako karty“: vybrané fragmenty v pořadí stromu, už vložené se přeskočí. */
export function selectionCandidates(roots: VaultNode[], selected: Set<string>): VaultNode[] {
  return flatten(roots).map((item) => item.node).filter((node) => selected.has(node.id) && node.kind === "brief" && !node.inserted);
}

/** Výchozí výběr MVP: co člověk potvrdil (mvp = yes) a ještě nemá kartu. */
export function defaultSelection(roots: VaultNode[]): Set<string> {
  return new Set(flatten(roots).map((item) => item.node).filter((node) => node.kind === "brief" && node.mvp === "yes" && !node.inserted).map((node) => node.id));
}

export function cardOf(node: VaultNode, index: number, parent: string | null, path: string[]): PlanCard {
  const kids = briefs(node);
  const where = [...path, node.title].join(" › ");
  return {
    ref: `f${index + 1}`,
    kind: "node",
    parent: parent ? "@" + parent : null,
    name: clip("[task] " + node.title, 160),
    purpose: clip("Zadání ze schránky: " + where, 1000),
    text: `Zadání karty žije ve schránce zadání: fragment „${clip(node.title, 120)}“ (revize textu r${textRevisionOf(node)})`
      + (kids.length ? ` a ${kids.length} podfragmentů jako bloky` : "")
      + ". Doslovný text dostane agent v node-brief (sekce fragments); sem se nekopíruje.",
    card: { status: "draft" },
    fragmentRef: [node, ...kids].slice(0, MAX_REFS).map((item) => ({ fragmentId: item.id })),
    blocks: kids.slice(0, MAX_BLOCKS).map((kid, number) => ({
      ref: `b${number + 1}`,
      title: clip(kid.title, 120),
      text: "Podfragment ze schránky; doslovný text v node-brief.fragments.",
      condition: clip(`Splněno podle podfragmentu „${kid.title}“.`, 400),
    })),
  };
}

/** Koncept dávky z kandidátů; nad strop dávky (200 karet) se zbytek přeskočí a ohlásí. */
export function buildPlan(roots: VaultNode[], candidates: VaultNode[], parent: string | null): VaultPlan {
  const paths = new Map(flatten(roots).map((item) => [item.node.id, item.path]));
  const chosen = candidates.slice(0, MAX_PLAN_CARDS);
  return {
    cards: chosen.map((node, index) => cardOf(node, index, parent, paths.get(node.id) ?? [])),
    skipped: candidates.length - chosen.length,
    fragments: chosen,
  };
}

/** Kam nové karty patří: schránka sektoru → do sektoru; karty → vedle ní (rodič karty); plátna → kořen. */
export function planParent(scope: string, nodes: { id: string; kind: string; parentId: string | null }[]): string | null {
  if (!scope) return null;
  const owner = nodes.find((node) => node.id === scope);
  if (!owner) return null;
  return owner.kind === "sector" ? owner.id : owner.parentId;
}

/** Tělo pro /api/canvas-plan (digest doplní volající). */
export function planBody(plan: VaultPlan) {
  return { nodes: plan.cards };
}
