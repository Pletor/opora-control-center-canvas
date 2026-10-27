// Úložiště technického modelu (`GET/PUT /api/studio/model?project=&domain=`, docs/studio.md §4) bez Reactu: adresa,
// obranné čtení odpovědi a zápis s optimistickou revizí. Model nikdy nesahá na `/api/graph`.
import { api, ApiError } from "@/shared/types/logic/types";
import { emptyStudioModel, STUDIO_MODEL_SCHEMA, type StudioModel } from "./model-types";

export function studioModelUrl(project: string, domain: string): string {
  return "/api/studio/model?" + new URLSearchParams({ project, domain });
}

const isObject = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);

/** Odpověď backendu jako model; neznámý tvar nebo cizí doména = prázdný model domény s revizí 0. Nehodí výjimku. */
export function normalizeStudioModel(raw: unknown, domain: string): StudioModel {
  if (!isObject(raw) || raw.schema !== STUDIO_MODEL_SCHEMA || raw.domainId !== domain || !Number.isInteger(raw.revision)
    || !Array.isArray(raw.nodes) || !Array.isArray(raw.edges)) return emptyStudioModel(domain);
  return { ...(raw as StudioModel), revision: raw.revision as number };
}

export type SaveResult = { kind: "saved"; model: StudioModel } | { kind: "conflict"; message: string } | { kind: "error"; message: string };

export function loadStudioModel(project: string, domain: string): Promise<StudioModel> {
  return api<unknown>(studioModelUrl(project, domain)).then((raw) => normalizeStudioModel(raw, domain));
}

/** Uloží model nad jeho `revision`; 409 = někdo uložil mezitím (konflikt), ostatní chyby jako text. */
export async function saveStudioModel(project: string, domain: string, model: StudioModel): Promise<SaveResult> {
  try {
    const raw = await api<unknown>(studioModelUrl(project, domain), { ...model, domainId: domain }, "PUT");
    return { kind: "saved", model: normalizeStudioModel(raw, domain) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) return { kind: "conflict", message: error.message };
    return { kind: "error", message: error instanceof Error ? error.message : String(error) };
  }
}
