import type { Project } from "@/shared/types/logic/types";

/**
 * Jediné místo, kde se chování rozhraní odvozuje od druhu projektu.
 * Vzhled ani ovládání se nikdy neukládají per projekt; liší se jen to, co projekt umí
 * (git projekt má main a oddělené pracovní prostory, lokální projekt jen návrh).
 * Nový projekt jakéhokoli druhu tak dostane stejné chování jako všechny ostatní téhož druhu.
 */
export type ProjectCapabilities = {
  /** Lokální složka, prázdný projekt nebo vestavěný návrh: bez git větví a worktree. */
  localProject: boolean;
  /** Historický vestavěný draft smí mít volné uzly bez sektoru. */
  legacyFree: boolean;
  /** Pracovní prostor, do kterého se projekt otevírá. */
  defaultWorkspace: "draft" | "main";
};

const LOCAL_KINDS = ["local", "empty", "builtin"];

export function isLocalKind(kind: string | undefined): boolean {
  return LOCAL_KINDS.includes(kind ?? "");
}

export function projectCapabilities(projectId: string, activeProject: Project | undefined): ProjectCapabilities {
  const isDraft = projectId === "draft";
  const kind = activeProject?.sourceKind ?? (isDraft ? "builtin" : undefined);
  const localProject = isDraft || isLocalKind(kind);
  return {
    localProject,
    legacyFree: isDraft && kind === "builtin",
    defaultWorkspace: localProject ? "draft" : "main",
  };
}
