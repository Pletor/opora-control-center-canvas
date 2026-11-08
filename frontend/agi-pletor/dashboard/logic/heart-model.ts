import { api } from "@/shared/types/logic/types";

export type HeartModel = { model: string; advisor: string; models: { id: string; label: string }[]; effort: string | null; efforts: string[] };

const URL = "/api/pletor/heart/model";

/** Rozumí jen tvaru `{model, advisor, models, effort, efforts}` (effort jen u hlavního modelu, poradce ho nemá); cokoli jiného je chyba čtení, ne tiché prázdno. */
export function parseHeartModel(raw: unknown): HeartModel {
  const r = (raw ?? {}) as Record<string, unknown>;
  if (typeof r.model !== "string" || typeof r.advisor !== "string" || !Array.isArray(r.models)) throw new Error("Model srdce se nepodařilo načíst.");
  const models = r.models.flatMap((m: { id?: unknown; label?: unknown }) => (typeof m?.id === "string" ? [{ id: m.id, label: typeof m.label === "string" ? m.label : m.id }] : []));
  const efforts = Array.isArray(r.efforts) ? r.efforts.filter((e): e is string => typeof e === "string") : [];
  return { model: r.model, advisor: r.advisor, models, effort: typeof r.effort === "string" && r.effort ? r.effort : null, efforts };
}

export const fetchHeartModel = (): Promise<HeartModel> => api<unknown>(URL).then(parseHeartModel);
export const putHeartModel = (model: string, advisor: string, effort: string): Promise<HeartModel> => api<unknown>(URL, { model, advisor, effort }, "PUT").then(parseHeartModel);
