// Rozhraní Správy webu (`backend/api/project/site_admin_routes.py`). Čte kdokoli, zapisuje jen člověk: doklad UI
// (cookie `opora_ui`) obstará sdílené `api` u každého zápisu samo. Uložení nese `expectedRevision`; jiná revize = 409.
import { api } from "@/shared/types/logic/types";
import type { SiteDocument } from "./site-document";

const BASE = "/api/site-admin";
const query = (project: string, extra: Record<string, string> = {}) => new URLSearchParams({ project, ...extra }).toString();

export type SiteFile = "tokens.css" | "tokens.json" | "README.md";
export const siteAdminUrls = {
  document: (project: string) => `${BASE}?${query(project)}`,
  file: (project: string, name: SiteFile) => `${BASE}/${name}?${query(project)}`,
  fonts: () => `${BASE}/fonts`,
  font: (project: string, name: string) => `${BASE}/fonts/${encodeURIComponent(name)}?${query(project)}`,
};

export type SiteView = { revision: number; document: SiteDocument };
export type SiteSaved = SiteView & { notes: string[] };

export const loadSiteAdmin = (project: string) => api<SiteView>(siteAdminUrls.document(project));

/** Uloží celý dokument nad revizí, ze které člověk vycházel. `revision` a `lastChange` píše jen server. */
export function saveSiteAdmin(project: string, expectedRevision: number, document: SiteDocument, note?: string): Promise<SiteSaved> {
  const { revision: _revision, lastChange: _lastChange, ...body } = document;
  return api<SiteSaved>(siteAdminUrls.document(project), { expectedRevision, document: body, ...(note ? { note } : {}) }, "PUT");
}

/** Vygenerovaný `tokens.css` uložené revize (text, ne JSON, proto mimo `api`). */
export async function loadTokensCss(project: string): Promise<string> {
  const response = await fetch(siteAdminUrls.file(project, "tokens.css"), { cache: "no-store" });
  if (!response.ok) throw new Error(`tokens.css není dostupné (HTTP ${response.status}).`);
  return response.text();
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
