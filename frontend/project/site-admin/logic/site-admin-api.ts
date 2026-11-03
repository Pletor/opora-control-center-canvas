// Rozhraní Správy webu (`backend/api/project/site_admin_routes.py`). Čte kdokoli, zapisuje jen člověk: doklad UI
// (cookie `opora_ui`) obstará sdílené `api` u každého zápisu samo. Uložení nese `expectedRevision`; jiná revize = 409.
import { api, ApiError } from "@/shared/types/logic/types";
import type { SiteDocument } from "./site-document";

const BASE = "/api/site-admin";
const query = (project: string, extra: Record<string, string> = {}) => new URLSearchParams({ project, ...extra }).toString();

export type SiteFile = "tokens.css" | "components.css" | "tokens.json" | "README.md";
export const siteAdminUrls = {
  document: (project: string) => `${BASE}?${query(project)}`,
  file: (project: string, name: SiteFile) => `${BASE}/${name}?${query(project)}`,
  fonts: () => `${BASE}/fonts`,
  font: (project: string, name: string) => `${BASE}/fonts/${encodeURIComponent(name)}?${query(project)}`,
  asset: (project: string, group: string, name: string) => `${BASE}/assets/${encodeURIComponent(group)}/${encodeURIComponent(name)}?${query(project)}`,
};

export type SiteView = { revision: number; document: SiteDocument };
export type SiteSaved = SiteView & { notes: string[] };

export const loadSiteAdmin = (project: string) => api<SiteView>(siteAdminUrls.document(project));

/** Uloží celý dokument nad revizí, ze které člověk vycházel. `revision` a `lastChange` píše jen server. */
export function saveSiteAdmin(project: string, expectedRevision: number, document: SiteDocument, note?: string): Promise<SiteSaved> {
  const { revision: _revision, lastChange: _lastChange, ...body } = document;
  return api<SiteSaved>(siteAdminUrls.document(project), { expectedRevision, document: body, ...(note ? { note } : {}) }, "PUT");
}

/** Vygenerovaný `tokens.css` nebo `components.css` uložené revize (text, ne JSON, proto mimo `api`). */
export async function loadSiteCss(project: string, name: "tokens.css" | "components.css" = "tokens.css"): Promise<string> {
  const response = await fetch(siteAdminUrls.file(project, name), { cache: "no-store" });
  if (!response.ok) throw new Error(`${name} není dostupné (HTTP ${response.status}).`);
  return response.text();
}

/** Odmítnuté vlastní CSS (422): cesta pole, řádek a důvod, aby editor ukázal chybu na řádku. */
export type SiteInvalid = { message: string; path: string; line: number; reason: string };

/** Chyba uložení → text pro pruh a případně odmítnuté vlastní CSS. FastAPI vrací 422 jako `{detail}`. */
export function saveProblem(failure: unknown): { message: string; invalid: SiteInvalid | null } {
  if (!(failure instanceof ApiError)) return { message: failure instanceof Error ? failure.message : String(failure), invalid: null };
  const detail = failure.body?.detail as unknown;
  if (detail && typeof detail === "object" && typeof (detail as SiteInvalid).line === "number") {
    const invalid = detail as SiteInvalid;
    return { message: invalid.message, invalid };
  }
  return { message: typeof detail === "string" ? detail : failure.message, invalid: null };
}

/** Nahraje soubor fontu do `site/fonts/`; vrátí cestu `fonts/<soubor>` pro záznam v `type.fonts`. */
export function uploadFont(project: string, name: string, data: string) {
  return api<{ file: string; size: number; type: string }>(siteAdminUrls.fonts(), { project, name, data });
}

/** Obsah souboru jako base64 bez hlavičky `data:` (tělo `POST /fonts`). */
export function fileToBase64(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(reader.error ?? new Error("Soubor se nepodařilo přečíst."));
    reader.readAsDataURL(file);
  });
}
