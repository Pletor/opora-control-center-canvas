// Zadání pro agenta z plátna toku (kontrakt plátna procesů §6): adresa čtení a načtení hotového markdownu.
// Text generuje backend (`GET /api/library/flows/{id}/brief`), frontend ho jen ukáže a zkopíruje.
import { api } from "@/shared/types/logic/types";

/** Adresa zadání; bez čísla verze server vezme aktivní verzi. */
export const briefUrl = (flow: string, version?: number | null): string =>
  `/api/library/flows/${encodeURIComponent(flow)}/brief${version ? `?${new URLSearchParams({ version: String(version) })}` : ""}`;

export const loadBrief = (flow: string, version?: number | null): Promise<string> =>
  api<{ markdown: string }>(briefUrl(flow, version)).then((made) => made.markdown);
