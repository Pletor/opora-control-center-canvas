// Příkazový řádek plátna toku (kontrakt plátna procesů §1b): kdy se otevře, jaký kontext jde srdci a jak se pozná, že
// srdce do plátna zapsalo. Čisté funkce bez Reactu; polling a odeslání skládá `use-command-bar.ts`.
import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import type { HeartContext } from "@/layout/heart-channel/logic/heart-api";

export const POLL_MS = 3000;
/** Po této době lišta „Srdce kreslí…“ řekne, že srdce zatím neodpovědělo (~3 min). */
export const LIMIT_MS = 180_000;
export const TIMEOUT_TEXT = "Srdce zatím neodpovědělo, zkontrolujte kanál Asistent.";

type KeyLike = { key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean; target: { tagName?: string; isContentEditable?: boolean } | null };

/** `/` nebo Ctrl+K otevře řádek, jen když fokus není v poli pro psaní (jinak by se `/` nedal napsat). */
export function opensCommandBar(event: KeyLike): boolean {
  const tag = event.target?.tagName?.toLowerCase();
  if (event.target?.isContentEditable || tag === "input" || tag === "textarea" || tag === "select") return false;
  if (event.altKey) return false;
  return (event.key === "/" && !event.ctrlKey && !event.metaKey) || ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k");
}

/** Kontext zprávy: plátno, zobrazená verze a vybrané uzly (bez výběru celé plátno, tedy bez `nodeIds`). */
export const flowContext = (flowId: string, versionId: string | null, nodeIds: readonly string[]): HeartContext =>
  ({ kind: "flow", flowId, ...(versionId ? { versionId } : {}), ...(nodeIds.length ? { nodeIds: [...nodeIds] } : {}) });

/** Uzly pro kontext: kliknutý uzel a uzly vybrané rámcem, bez duplicit a bez uzlů, které na plátně už nejsou. */
export const commandNodeIds = (clicked: string | null, picked: readonly string[], existing: readonly string[]): string[] =>
  [...new Set([...(clicked ? [clicked] : []), ...picked])].filter((id) => existing.includes(id));

/** Verze plátna v okamžiku odeslání: id → hash. */
export const snapshotOf = (versions: readonly FlowVersion[]): ReadonlyMap<string, string> => new Map(versions.map((version) => [version.id, version.hash]));

/** Nejnovější draft, který od odeslání přibyl nebo změnil obsah (srdce smí psát do existujícího draftu); jinak null. */
export function heartWrote(known: ReadonlyMap<string, string>, versions: readonly FlowVersion[]): FlowVersion | null {
  return versions.filter((version) => version.status === "draft" && known.get(version.id) !== version.hash).at(-1) ?? null;
}
