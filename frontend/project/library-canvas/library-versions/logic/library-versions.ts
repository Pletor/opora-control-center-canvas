// Verze plátna toku na liště (kontrakt knihovny §1: draft → active s historií a návratem, bez schválení). Zobrazená
// verze je vybraná, jinak novější draft, jinak aktivní, jinak nejnovější. Akce podle stavu zobrazené verze: draft jde
// aktivovat, vyřazenou verzi jde vrátit (aktivovat znovu), u aktivní jde návrat na předchozí vyřazenou.
import type { FlowVersion, VersionStatus } from "@/shared/flow-editor/logic/flow-types";

export const STATUS_LABEL: Record<VersionStatus, string> = { draft: "draft", candidate: "kandidát", active: "aktivní", retired: "historie" };

export function pickFlowVersion(versions: readonly FlowVersion[], wanted: string | null): FlowVersion | null {
  const active = versions.find((item) => item.status === "active") ?? null;
  const drafts = versions.filter((item) => item.status === "draft" && item.n > (active?.n ?? 0));
  return versions.find((item) => item.id === wanted) ?? drafts.at(-1) ?? active ?? versions.at(-1) ?? null;
}

export type VersionAction = "activate" | "restore" | "rollback" | null;

/** Co jde s neupravenou zobrazenou verzí udělat. */
export function versionAction(versions: readonly FlowVersion[], viewing: FlowVersion | null): VersionAction {
  if (!viewing) return null;
  if (viewing.status === "draft" || viewing.status === "candidate") return "activate";
  if (viewing.status === "retired") return "restore";
  return versions.some((item) => item.status === "retired" && item.n < viewing.n) ? "rollback" : null;
}

/** Čekající návrh srdce u plátna člověka (knihovna §5): nejnovější draft s `proposedBy` novější než aktivní verze. */
export function pendingProposal(versions: readonly FlowVersion[]): FlowVersion | null {
  const active = versions.find((item) => item.status === "active")?.n ?? 0;
  return versions.filter((item) => item.status === "draft" && item.n > active && item.meta?.proposedBy).at(-1) ?? null;
}

/** Historie od nejnovější verze dolů. */
export const history = (versions: readonly FlowVersion[]) => [...versions].sort((a, b) => b.n - a.n);
