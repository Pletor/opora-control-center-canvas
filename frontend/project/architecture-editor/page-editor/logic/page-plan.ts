// Plán stránky ze serveru (`GET /api/page-plan`, docs/navrhy/2026-11-10-platno-2.md „Obsluha agenty“): plátno z něj čte
// jen to, co graf nenese, tedy které boxy mají uloženou skicu (`sections[].sketch`). Layout a logika jdou z grafu.
// Tolerantní převod (chybějící pole = žádná skica), síť jen v `useSketchedBoxes`. Test vedle.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";

/** Id sekcí, jejichž `sketch` má kladnou revizi. */
export function sketchedBoxes(raw: unknown): Set<string> {
  const sections = raw && typeof raw === "object" && Array.isArray((raw as { sections?: unknown }).sections) ? (raw as { sections: unknown[] }).sections : [];
  const ids = new Set<string>();
  for (const item of sections) {
    const section = item as { id?: unknown; sketch?: { revision?: unknown } | null } | null;
    if (typeof section?.id === "string" && typeof section.sketch?.revision === "number" && section.sketch.revision > 0) ids.add(section.id);
  }
  return ids;
}

/** Boxy se skicou otevřené stránky; obnoví se se změnou stránky (`revision` = otisk sekcí) nebo po uložení skici (`bump`).
 * Nedostupný endpoint (starší server) = žádné značky skici, plátno jede dál. */
export function useSketchedBoxes(project: string, workspace: string, pageId: string | null, revision: string) {
  const [ids, setIds] = useState<ReadonlySet<string>>(new Set());
  const [bump, setBump] = useState(0);
  useEffect(() => {
    let alive = true;
    if (!pageId) { setIds(new Set()); return; }
    api<unknown>("/api/page-plan?" + new URLSearchParams({ project, workspace, pageId }))
      .then((value) => { if (alive) setIds(sketchedBoxes(value)); }, () => { if (alive) setIds(new Set()); });
    return () => { alive = false; };
  }, [project, workspace, pageId, revision, bump]);
  return { ids, refresh: () => setBump((value) => value + 1) };
}
