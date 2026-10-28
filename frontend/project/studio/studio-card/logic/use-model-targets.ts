// Načte id karet s cílem z MODELu pro doménu, kterou Skutečnost právě ukazuje (docs/studio.md §4a). Jen čte
// `GET /api/studio/model`; chyba nebo doména bez modelu = žádný odznak. Odpověď předběhnutá změnou domény se zahodí.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { studioModelUrl } from "../../model/logic/studio-model-api";
import { modelBindingIds } from "./model-targets";

const NONE: ReadonlySet<string> = new Set();

/** `domain` null (úroveň projektu) nebo `enabled` false (vrstva MODEL) = nic nenačítá. */
export function useModelTargets(project: string, domain: string | null, enabled: boolean): ReadonlySet<string> {
  const [ids, setIds] = useState<ReadonlySet<string>>(NONE);
  useEffect(() => {
    setIds(NONE);
    if (!project || !domain || !enabled) return;
    let current = true;
    api<unknown>(studioModelUrl(project, domain))
      .then((raw) => { if (current) setIds(modelBindingIds(raw, domain)); })
      .catch(() => { if (current) setIds(NONE); });
    return () => { current = false; };
  }, [project, domain, enabled]);
  return ids;
}
