// Karta profilu bez Reactu: rozepsaná volba architektury a uživatelů, než ji uživatel uloží pro
// projekt. Druhý klik na vybranou volbu ji zruší (zpět na „nenastaveno“), aby šlo profil i vyprázdnit.
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";

export type ProfileDraft = Pick<ProjectProfile, "architecture" | "tenancy">;

export const draftOf = (profile: ProjectProfile): ProfileDraft => ({ architecture: profile.architecture, tenancy: profile.tenancy });

export function chooseArchitecture(draft: ProfileDraft, value: ProjectProfile["architecture"]): ProfileDraft {
  return { ...draft, architecture: draft.architecture === value ? "" : value };
}

export function chooseTenancy(draft: ProfileDraft, value: ProjectProfile["tenancy"]): ProfileDraft {
  return { ...draft, tenancy: draft.tenancy === value ? "" : value };
}

/** Uložit má smysl jen tehdy, když se rozepsaná volba liší od uloženého profilu. */
export function draftChanged(draft: ProfileDraft, profile: ProjectProfile): boolean {
  return draft.architecture !== profile.architecture || draft.tenancy !== profile.tenancy;
}
