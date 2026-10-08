// Vazba profilu projektu na API: načte nastavení otevřeného projektu (`GET /api/project-settings`)
// a uloží změnu profilu se stejnou revizí, jakou četl (`expected_revision`). Kolize (nastavení se
// mezitím změnilo jinde) přijde jako česká chyba ze serveru a zůstane v `error`, dokud uživatel
// nenačte nastavení znovu. Volá ho jen rodič (App); šuplík ani karta nic nenačítají ani neukládají.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type SettingsSnapshot } from "@/shared/types/logic/types";
import type { ProfileDraft } from "./profile-card";
import { trackSaveWrite } from "@/shared/hooks/logic/save-coordinator";

export type ProjectProfileApi = {
  snapshot: SettingsSnapshot | null;
  saving: boolean;
  error: string;
  /** Uloží profil pro projekt; `true`, když server změnu přijal. */
  save: (draft: ProfileDraft) => Promise<boolean>;
  /** Načte uložené nastavení znovu (po kolizi nebo po otevření šuplíku). */
  reload: () => void;
};

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function useProjectProfile(project: string, reloadKey: unknown): ProjectProfileApi {
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const ticket = useRef(0);
  const [reloads, setReloads] = useState(0);

  // Jiný projekt = jiný profil: starý se zahodí hned, aby šuplík neukazoval cizí profil ani chvíli.
  useEffect(() => { setSnapshot(null); }, [project]);
  useEffect(() => {
    const current = ++ticket.current;
    api<SettingsSnapshot>("/api/project-settings?" + new URLSearchParams({ project }))
      .then((value) => {
        if (current !== ticket.current) return;
        setSnapshot(value);
        setError("");
      })
      .catch((reason) => { if (current === ticket.current) setError(message(reason)); });
  }, [project, reloadKey, reloads]);

  const save = useCallback(async (draft: ProfileDraft) => {
    if (!snapshot) return false;
    const current = ++ticket.current;
    setSaving(true);
    setError("");
    try {
      const value = await trackSaveWrite(project, "*", api<SettingsSnapshot>("/api/project-settings", {
        project,
        expected_revision: snapshot.revision,
        name: snapshot.project.name,
        settings: { ...snapshot.settings, ...draft },
      }));
      if (current === ticket.current) setSnapshot(value);
      return true;
    } catch (reason) {
      if (current === ticket.current) setError(message(reason));
      return false;
    } finally {
      setSaving(false);
    }
  }, [project, snapshot]);

  const reload = useCallback(() => setReloads((count) => count + 1), []);
  return { snapshot, saving, error, save, reload };
}
