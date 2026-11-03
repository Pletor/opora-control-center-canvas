// Stav stránky Správa webu: uložený dokument s revizí, rozepsaný dokument, uložení s optimistickým zámkem (409 =
// někdo uložil mezitím) a vygenerovaný `tokens.css` uložené revize pro náhledy. Jediné místo, které na stránce zapisuje.
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/shared/types/logic/types";
import { fileToBase64, loadSiteAdmin, loadTokensCss, saveSiteAdmin, uploadFont } from "./site-admin-api";
import type { SiteDocument } from "./site-document";

export type SiteAdminState = ReturnType<typeof useSiteAdmin>;
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useSiteAdmin(project: string) {
  const [revision, setRevision] = useState(0);
  const [saved, setSaved] = useState<SiteDocument | null>(null);
  const [draft, setDraft] = useState<SiteDocument | null>(null);
  const [tokensCss, setTokensCss] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [notes, setNotes] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const ticket = useRef(0);

  const refreshCss = useCallback(() => { loadTokensCss(project).then(setTokensCss, () => setTokensCss("")); }, [project]);
  const load = useCallback(async () => {
    const mine = ++ticket.current;
    setLoading(true); setError("");
    try {
      const view = await loadSiteAdmin(project);
      if (mine !== ticket.current) return;
      setRevision(view.revision); setSaved(view.document); setDraft(view.document); setConflict(false); setNotes([]);
      refreshCss();
    } catch (failure) { if (mine === ticket.current) setError(message(failure)); }
    finally { if (mine === ticket.current) setLoading(false); }
  }, [project, refreshCss]);
  useEffect(() => { void load(); return () => { ticket.current++; }; }, [load]);

  async function save(over = revision) {
    if (!draft || saving) return;
    setSaving(true); setError("");
    try {
      const result = await saveSiteAdmin(project, over, draft);
      setRevision(result.revision); setSaved(result.document); setDraft(result.document); setNotes(result.notes); setConflict(false);
      refreshCss();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) setConflict(true); else setError(message(failure));
    } finally { setSaving(false); }
  }
  /** Konflikt: uložit moje rozepsané nad novou revizí (přepíše cizí změnu), nebo ji načíst a moje zahodit. */
  async function overwrite() {
    try { const latest = await loadSiteAdmin(project); await save(latest.revision); }
    catch (failure) { setError(message(failure)); }
  }
  async function upload(file: File, record: (path: string) => (document: SiteDocument) => SiteDocument) {
    setUploading(true); setUploadError("");
    try {
      const stored = await uploadFont(project, file.name, await fileToBase64(file));
      setDraft((current) => current && record(stored.file)(current));
    } catch (failure) { setUploadError(message(failure)); }
    finally { setUploading(false); }
  }
  const change = (update: (document: SiteDocument) => SiteDocument) => setDraft((current) => current && update(current));
  return { revision, saved, draft, dirty: draft !== saved, tokensCss, loading, saving, error, conflict, notes, uploading, uploadError,
    change, save: () => save(), overwrite, reload: load, upload, dismissNotes: () => setNotes([]) };
}
