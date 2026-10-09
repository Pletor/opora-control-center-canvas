import { useCallback, useEffect, useRef, useState } from "react";
import { api, type View } from "@/shared/types/logic/types";
import { saveWriteRevision } from "@/shared/hooks/logic/save-coordinator";
import { withSavedVersion, type CanvasVersion, type CanvasVersions } from "./save-versions";

export type CanvasVersionsState = {
  versions: CanvasVersion[]; dirty: boolean; loading: boolean; saving: boolean; error: string;
  currentToken: string; externalChanged: boolean;
  refresh: (accept?: boolean) => Promise<CanvasVersions>;
  preflight: () => Promise<void>;
  save: (digest: string, author: string, expectedToken: string) => Promise<void>;
  restore: (versionId: string, digest: string, author: string, expectedToken: string) => Promise<View>;
};

/** Server fingerprints observe all covered content; polling never replaces local editor drafts. */
export function useCanvasVersions({ project, workspace, enabled, refreshKey, paused = false }: {
  project: string; workspace: string; enabled: boolean; refreshKey: string; paused?: boolean;
}): CanvasVersionsState {
  const [versions, setVersions] = useState<CanvasVersion[]>([]);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [currentToken, setToken] = useState("");
  const [externalChanged, setExternal] = useState(false);
  const scope = JSON.stringify([project, workspace]);
  const latest = useRef({ scope, token: "", writeRevision: 0, read: 0 });
  if (latest.current.scope !== scope) latest.current = { scope, token: "", writeRevision: saveWriteRevision(project, workspace), read: latest.current.read + 1 };
  const refresh = useCallback(async (accept = false) => {
    if (latest.current.scope !== scope) throw new Error("Pracovní prostor se změnil.");
    const owner = latest.current; const ticket = ++owner.read;
    const ownRevision = saveWriteRevision(project, workspace);
    const result = await api<CanvasVersions>("/api/canvas-versions?" + new URLSearchParams({ project, workspace }));
    if (latest.current !== owner || ticket !== owner.read) return result;
    if (!result.currentToken) throw new Error("Server neposkytl otisk uloženého pracovního prostoru.");
    const external = !!owner.token && owner.token !== result.currentToken && owner.writeRevision === ownRevision;
    if (accept || !owner.token || !external) { owner.token = result.currentToken; setToken(result.currentToken); }
    if (accept) setExternal(false); else if (external) setExternal(true);
    owner.writeRevision = ownRevision;
    setVersions(result.versions ?? []); setDirty(result.dirty); setError("");
    return result;
  }, [project, workspace, scope]);
  useEffect(() => { setToken(""); setExternal(false); setSaving(false); setError(""); setVersions([]); setDirty(false); }, [scope]);
  useEffect(() => {
    if (!enabled) { setVersions([]); setToken(""); setExternal(false); setLoading(false); return; }
    const owner = latest.current;
    setLoading(true);
    void refresh().catch((cause) => { if (latest.current === owner) setError(String(cause)); }).finally(() => { if (latest.current === owner) setLoading(false); });
  }, [enabled, refreshKey, refresh]);
  useEffect(() => {
    if (!enabled || paused || saving) return;
    const owner = latest.current;
    const check = () => { void refresh().catch((cause) => { if (latest.current === owner) setError(String(cause)); }); };
    const timer = window.setInterval(check, 3000); window.addEventListener("focus", check);
    return () => { clearInterval(timer); window.removeEventListener("focus", check); };
  }, [enabled, paused, saving, refresh]);
  async function save(digest: string, author: string, expectedToken: string) {
    const owner = latest.current; setSaving(true);
    try {
      const result = await api<{ version: CanvasVersion; dirty: boolean; currentToken: string }>("/api/canvas-versions", { project, workspace, digest, author, expectedToken });
      if (latest.current !== owner) return;
      owner.read++; owner.token = result.currentToken; owner.writeRevision = saveWriteRevision(project, workspace);
      setVersions((items) => withSavedVersion(items, result.version)); setDirty(result.dirty); setToken(result.currentToken); setExternal(false);
    } finally { if (latest.current === owner) setSaving(false); }
  }
  async function restore(versionId: string, digest: string, author: string, expectedToken: string) {
    const owner = latest.current;
    const result = await api<{ view: View }>("/api/canvas-versions/restore", { project, workspace, versionId, digest, author, expectedToken });
    if (latest.current !== owner) return result.view;
    await refresh(true).catch((cause) => setError(String(cause))); return result.view;
  }
  async function preflight() {
    if (externalChanged) throw new Error("Pracovní prostor změnil jiný proces. Načtěte aktuální stav a porovnejte rozepsané změny.");
    const before = latest.current.token;
    const ownWrites = latest.current.writeRevision !== saveWriteRevision(project, workspace);
    const result = await refresh();
    if (before && before !== result.currentToken && !ownWrites) throw new Error("Pracovní prostor se mezitím změnil mimo toto okno. Nejprve načtěte aktuální stav.");
  }
  return { versions, dirty, loading, saving, error, currentToken, externalChanged, refresh, preflight, save, restore };
}
