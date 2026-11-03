// Verze workflow jako štítky pro lištu: číslo, stav česky a vztah ke zobrazené verzi. Výchozí srovnání je rodič
// zobrazené verze (co tato verze změnila), u první verze nic.
import type { FlowVersion, VersionStatus } from "@/shared/flow-editor/logic/flow-types";

export const VERSION_STATUS_LABEL: Record<VersionStatus, string> = { draft: "draft", candidate: "kandidát", active: "aktivní", retired: "vyřazená" };
export type VersionChip = { id: string; label: string; status: VersionStatus; statusLabel: string; current: boolean; title: string };

export function versionChips(versions: readonly FlowVersion[], viewing: string | null): VersionChip[] {
  return [...versions].sort((a, b) => b.n - a.n).map((version) => ({
    id: version.id, label: `v${version.n}`, status: version.status, statusLabel: VERSION_STATUS_LABEL[version.status] ?? version.status,
    current: version.id === viewing, title: `v${version.n} · ${version.hash.slice(0, 10)} · ${new Date(version.created_at).toLocaleString("cs-CZ")}`
      + (version.eval_run_id ? ` · eval ${version.eval_run_id}` : ""),
  }));
}

export function defaultCompare(versions: readonly FlowVersion[], viewing: FlowVersion | null): string | null {
  if (!viewing) return null;
  if (viewing.parent_version_id && versions.some((item) => item.id === viewing.parent_version_id)) return viewing.parent_version_id;
  return null;
}
