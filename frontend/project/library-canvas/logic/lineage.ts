// Rodokmen plátna toku (kontrakt knihovny §1): „vychází z <prvek>@<verze>“, upozornění, že zdroj má v knihovně
// novější aktivní verzi, a kolik prvků a projektů z plátna vychází. Používá ho plátno knihovny i odkaz u domény
// a stránky v projektu.
import type { LearnedFrom } from "@/shared/flow-editor/logic/flow-types";
import type { DerivedFrom } from "./library-api";

type Source = { title: string; activeN: number | null; versions: { id: string; n: number }[] };
export type Lineage = { from: string | null; newer: string | null; derived: string | null };

export function sourceVersion(derivedFrom: DerivedFrom | null, source: Source | null): number | null {
  return derivedFrom && source ? source.versions.find((version) => version.id === derivedFrom.versionId)?.n ?? null : null;
}

export function lineageOf(flow: { derivedFrom: DerivedFrom | null; derived?: { projectId: string | null }[] }, source: Source | null, projectName: (id: string) => string = (id) => id): Lineage {
  const n = sourceVersion(flow.derivedFrom, source);
  const from = !flow.derivedFrom ? null : source ? `vychází z ${source.title}@v${n ?? "?"}` : "vychází z prvku, který už v knihovně není";
  const newer = source && n !== null && source.activeN !== null && source.activeN > n ? `v knihovně je novější v${source.activeN}` : null;
  const derived = flow.derived ?? [];
  const projects = new Set(derived.flatMap((item) => item.projectId ? [projectName(item.projectId)] : []));
  return { from, newer, derived: derived.length ? `odvozené: ${derived.length}${projects.size ? ` · v projektech: ${[...projects].join(", ")}` : ""}` : null };
}

const RESULT: Record<string, string> = { verified: "ověřeno", delivered: "odevzdáno", failed: "neprošlo" };

/** Původ plátna agenta (knihovna §5 `learnedFrom`): „naučeno v projektu Ample · karta rag · ověřeno“. */
export function learnedText(learned: LearnedFrom | null | undefined, projectName: (id: string) => string = (id) => id): string | null {
  if (!learned) return null;
  return [`naučeno v projektu ${projectName(learned.project)}`, learned.card && `karta ${learned.card}`, RESULT[learned.result] ?? learned.result].filter(Boolean).join(" · ");
}
