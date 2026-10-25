import { isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";

// Připojení GitHub repozitáře k projektu z lokální složky (docs/oporahub-github.md). Server ověří origin
// složky na disku; klient jen posílá, co člověk potvrdil, a nic neodvozuje z druhu projektu.
export type FolderBinding = { repository: string; branch: string; boundAt: string };
export type FolderRepositoryStatus = {
  project: string; applies: boolean; bindable: boolean; binding: FolderBinding | null;
  detectedRepository: string | null; canConfigure: boolean; unavailableReason: string | null;
};

export const ROOT = "/api/oporahub/repository";
export const statusUrl = (project: string) => `${ROOT}?${new URLSearchParams({ project })}`;
const REPOSITORY = /^[A-Za-z0-9-]+\/[A-Za-z0-9_-][A-Za-z0-9._-]*$/;
const BRANCH = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$/;

function binding(value: unknown): value is FolderBinding {
  return isObject(value) && isText(value.repository, 255) && isText(value.branch, 200) && isText(value.boundAt, 64);
}

export function parseStatus(raw: unknown): FolderRepositoryStatus {
  if (!isObject(raw) || !isText(raw.project, 64) || typeof raw.applies !== "boolean" || typeof raw.bindable !== "boolean"
    || typeof raw.canConfigure !== "boolean" || !(raw.binding === null || binding(raw.binding))
    || !(raw.detectedRepository === null || isText(raw.detectedRepository, 255))
    || !(raw.unavailableReason === null || isText(raw.unavailableReason, 400))) throw new Error("Stav repozitáře projektu má neplatný tvar.");
  return raw as FolderRepositoryStatus;
}

/** Tělo připojení, nebo null, dokud repozitář a větev nemají platný tvar. */
export function bindPayload(project: string, repository: string, branch: string) {
  const name = repository.trim(), ref = branch.trim();
  if (!REPOSITORY.test(name) || name.includes("..") || !BRANCH.test(ref) || ref.includes("..")) return null;
  return { project, repository: name, branch: ref };
}
