import type { Architecture, Platform, Project, Tenancy } from "@/shared/types/logic/types";

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

/**
 * Profil projektu pro katalogy Knihovny a Agentů (docs/suplik-a-profil.md). Profil popisuje projekt,
 * ne vzhled: podle něj se zúží výběr, rozhraní zůstává stejné. `""` znamená nenastaveno a podle
 * takového pole se nic nefiltruje. Dílek nastavení nečte — dostane hotový profil v props od App.
 */
export type ProjectProfile = { architecture: Architecture | ""; tenancy: Tenancy | ""; platform: Platform };

const ARCHITECTURES: Architecture[] = ["monolith", "modular", "microservices", "serverless"];
const TENANCIES: Tenancy[] = ["single", "multi"];
const PLATFORMS: Platform[] = ["web", "app", "component"];

/** Nastavení (i chybějící nebo starší bez profilu) na profil; neznámá hodnota se čte jako nenastaveno. */
export function catalogProfile(settings: { architecture?: string; tenancy?: string; platform?: string } | null): ProjectProfile {
  const architecture = ARCHITECTURES.find((value) => value === settings?.architecture) ?? "";
  const tenancy = TENANCIES.find((value) => value === settings?.tenancy) ?? "";
  const platform = PLATFORMS.find((value) => value === settings?.platform) ?? "web";
  return { architecture, tenancy, platform };
}

/** Profil, který nic neříká: ani architektura, ani uživatelé. Šuplík pak nabídne kartu profilu. */
export function profileUnset(profile: ProjectProfile): boolean {
  return !profile.architecture && !profile.tenancy;
}
