import { isCount, isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";

// Kniha důkazů (docs/oporahub-verification.md, „Kniha důkazů“): jeden řádek na teorém nebo vlastnost
// modelu s posledním strojově zkontrolovaným stavem. Jen ke čtení.
export const LEDGER_STATUSES = ["proved", "checked", "counterexample", "failed", "unverified", "unchecked"] as const;
export type LedgerStatus = typeof LEDGER_STATUSES[number];
export type LedgerEntry = {
  id: string; tool: string; kind: string; name: string; source: string | null; declared: boolean; status: string;
  commitSha: string | null; axioms: string[] | null; trust: string | null; lastChecked: string | null;
  verificationId: string | null; checkName: string | null;
};
export type Ledger = { schemaVersion: number; allowedAxioms: string[]; counts: Record<string, number>; entries: LedgerEntry[] };
export const STATUS_META: Record<string, { glyph: string; word: string; tone: "ok" | "warn" | "bad" | "gap" }> = {
  proved: { glyph: "✓", word: "dokázáno", tone: "ok" }, checked: { glyph: "✓", word: "zkontrolováno", tone: "ok" },
  counterexample: { glyph: "✕", word: "protipříklad", tone: "bad" }, failed: { glyph: "✕", word: "selhalo", tone: "bad" },
  unverified: { glyph: "◷", word: "neověřeno", tone: "warn" }, unchecked: { glyph: "◌", word: "nezkontrolováno", tone: "gap" },
};
export const statusMeta = (status: string) => STATUS_META[status] ?? { glyph: "◷", word: status, tone: "warn" as const };

const opt = (value: unknown) => isText(value) ? value : null;
const texts = (value: unknown) => Array.isArray(value) ? value.filter(item => isText(item)) as string[] : null;

function entry(raw: unknown): LedgerEntry | null {
  if (!isObject(raw) || !isText(raw.id) || !isText(raw.tool) || !isText(raw.status)) return null;
  return { id: raw.id, tool: raw.tool, kind: isText(raw.kind) ? raw.kind : "?", name: isText(raw.name) ? raw.name : raw.id,
    source: opt(raw.source), declared: raw.declared !== false, status: raw.status, commitSha: opt(raw.commitSha),
    axioms: texts(raw.axioms), trust: opt(raw.trust), lastChecked: opt(raw.lastChecked),
    verificationId: opt(raw.verificationId), checkName: opt(raw.checkName) };
}
export function parseLedger(raw: unknown): Ledger {
  if (!isObject(raw) || !Array.isArray(raw.entries) || !isObject(raw.counts)) throw new Error("Kniha důkazů má neplatný tvar.");
  return { schemaVersion: isCount(raw.schemaVersion) ? raw.schemaVersion : 0, allowedAxioms: texts(raw.allowedAxioms) ?? [],
    counts: Object.fromEntries(Object.entries(raw.counts).filter(([, value]) => isCount(value))) as Record<string, number>,
    entries: raw.entries.map(entry).filter((item): item is LedgerEntry => item !== null) };
}
export const ledgerEndpoint = (project: string, workspace: string) =>
  `/api/oporahub/verifications/ledger?${new URLSearchParams({ project, workspace })}`;

export type LedgerFilter = { tool: "all" | "lean" | "tlc" | "conformance"; status: "all" | string };
export type LedgerRow = LedgerEntry & { glyph: string; word: string; tone: "ok" | "warn" | "bad" | "gap";
  commit: string; trustLabel: string; foreignAxioms: string[] };

/** Dlaždice počtů v pevném pořadí stavů; neznámý stav ze serveru se přidá na konec. */
export function ledgerTiles(ledger: Ledger) {
  const keys = [...LEDGER_STATUSES, ...Object.keys(ledger.counts).filter(key => !(LEDGER_STATUSES as readonly string[]).includes(key))];
  return keys.map(status => ({ status, count: ledger.counts[status] ?? 0, ...statusMeta(status) }));
}
export function ledgerRows(ledger: Ledger, filter: LedgerFilter): LedgerRow[] {
  const allowed = new Set(ledger.allowedAxioms);
  return ledger.entries.filter(item => (filter.tool === "all" || item.tool === filter.tool) && (filter.status === "all" || item.status === filter.status))
    .map(item => ({ ...item, ...statusMeta(item.status), commit: item.commitSha?.slice(0, 12) ?? "—",
      trustLabel: item.trust === "ci-verified" ? "ověřeno CI" : item.trust === "agent-reported" ? "nahlášeno agentem" : "—",
      foreignAxioms: (item.axioms ?? []).filter(axiom => !allowed.has(axiom)) }));
}
