// Dvě stopy Schránky (docs/navrh-schranka-zadani.md, „Dvě stopy a levé menu“): CX/UX/UI (jak věc vypadá
// a co dělá) a Backend + DB (jak funguje, funkce a metody, data). Fragmenty bez stopy jsou „Nezařazené“.
// Přepínač stop je jen filtr pohledu: strom se zúží na vybranou stopu a předci jiné stopy zůstanou jako
// cesta ke kořeni (`offTrack`), aby strom zůstal souvislý. Poslední volba se pamatuje jednou pro aplikaci.
// Bez Reactu.
import { coverageOf, type Track, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";

export type TrackView = Track | "none";
export const TRACK_VIEWS: { id: TrackView; label: string; hint: string }[] = [
  { id: "ux", label: "CX/UX/UI", hint: "Tok uživatele, obrazovky, stavy, texty a náčrty. Karty vzniknou ve vrstvě frontend." },
  { id: "logic", label: "Backend + DB", hint: "Pravidla, výpočty, funkce a metody, datový model a API. Karty vzniknou ve vrstvě backend." },
  { id: "none", label: "Nezařazené", hint: "Fragmenty z doby před stopami. Karty vzniknou bez vrstvy." },
];

export const trackLabel = (track: TrackView): string => TRACK_VIEWS.find((item) => item.id === track)?.label ?? "";

/** Platná stopa uzlu: od serveru `effectiveTrack`, u staršího serveru vlastní `track` nebo zděděná. */
export function viewOf(node: Pick<VaultNode, "track" | "effectiveTrack">, inherited: Track | null = null): TrackView {
  const effective = node.effectiveTrack !== undefined ? node.effectiveTrack : (node.track ?? inherited);
  return effective ?? "none";
}

/** Strom jedné stopy: shoda zůstane celá se svými shodnými potomky, předek jiné stopy jen jako cesta (`offTrack`). */
export function filterByTrack(roots: VaultNode[], track: TrackView): VaultNode[] {
  const keep = (node: VaultNode, inherited: Track | null): VaultNode | null => {
    const view = viewOf(node, inherited);
    const own = view === "none" ? null : view;
    const children = node.children.map((child) => keep(child, own)).filter((child): child is VaultNode => !!child);
    if (view === track) return { ...node, offTrack: false, children };
    return children.length ? { ...node, offTrack: true, children } : null;
  };
  return roots.map((root) => keep(root, null)).filter((root): root is VaultNode => !!root);
}

/** Počet kapitol (listů zadání) v každé stopě pro čipy přepínače. */
export function trackCounts(roots: VaultNode[]): Record<TrackView, number> {
  return {
    ux: coverageOf(filterByTrack(roots, "ux")).leaves,
    logic: coverageOf(filterByTrack(roots, "logic")).leaves,
    none: coverageOf(filterByTrack(roots, "none")).leaves,
  };
}

/** Zobrazená stopa: zapamatovaná volba, jinak první stopa s obsahem (prázdná schránka = CX/UX/UI). */
export function pickTrack(stored: TrackView | null, counts: Record<TrackView, number>): TrackView {
  if (stored) return stored;
  return TRACK_VIEWS.find((item) => counts[item.id] > 0)?.id ?? "ux";
}

/** Jediný klíč pro celou aplikaci. Nikdy se do něj nepřidává id projektu. */
export const VAULT_TRACK_KEY = "opora:vault-track:v1";

/** Uložená volba je cizí text: neznámá hodnota nebo rozbitý JSON znamená „žádná“. */
export function parseTrack(raw: string | null): TrackView | null {
  try {
    const value = raw ? (JSON.parse(raw) as { track?: unknown } | null) : null;
    const track = value?.track;
    return track === "ux" || track === "logic" || track === "none" ? track : null;
  } catch {
    return null;
  }
}

export function readTrack(): TrackView | null {
  try { return parseTrack(localStorage.getItem(VAULT_TRACK_KEY)); } catch { return null; }
}

export function writeTrack(track: TrackView): void {
  try { localStorage.setItem(VAULT_TRACK_KEY, JSON.stringify({ track })); } catch { /* bez úložiště jen v paměti */ }
}

/**
 * Kam patří fragment z Podnětu: pod kořen vybrané stopy (zdědí ji; kořen jiné stopy je v pohledu jen
 * cesta), jinak nový kořen se stopou. Nový kořen bez stopy server odmítne, proto u „Nezařazené“ musí
 * stopu zvolit člověk (`chosen`); bez ní vrátí `null`.
 */
export function ideaTarget(roots: VaultNode[], vaultScope: string, track: TrackView, chosen: Track | null):
  { parentId: string } | { scopeNodeId: string; track: Track } | null {
  const root = roots.find((item) => !item.offTrack);
  if (root) return { parentId: root.id };
  const rootTrack = track === "none" ? chosen : track;
  return rootTrack ? { scopeNodeId: vaultScope, track: rootTrack } : null;
}
