// Technický model domény pro vrstvu MODEL (docs/studio.md §4): načte ho při změně projektu nebo domény a uloží nad
// revizí, ze které vychází. Konflikt (409) se hlásí stavem `conflict` a model zůstává, jak ho člověk upravil; `reload`
// načte aktuální verzi. Odpověď, kterou mezitím předběhla změna domény, se zahodí. Zatím bez UI (S6).
import { useCallback, useEffect, useRef, useState } from "react";
import { emptyStudioModel, type StudioModel } from "./model-types";
import { loadStudioModel, saveStudioModel } from "./studio-model-api";

export type StudioModelStatus = "loading" | "ready" | "saving" | "conflict" | "error";

export function useStudioModel(project: string, domain: string) {
  const [model, setModel] = useState<StudioModel>(() => emptyStudioModel(domain));
  const [status, setStatus] = useState<StudioModelStatus>("loading");
  const [message, setMessage] = useState("");
  const scope = useRef(0);

  const reload = useCallback(() => {
    const ticket = ++scope.current;
    setStatus("loading");
    loadStudioModel(project, domain)
      .then((loaded) => { if (ticket === scope.current) { setModel(loaded); setStatus("ready"); setMessage(""); } })
      .catch((error) => { if (ticket === scope.current) { setStatus("error"); setMessage(error instanceof Error ? error.message : String(error)); } });
  }, [project, domain]);

  useEffect(() => {
    if (!project || !domain) return;
    setModel(emptyStudioModel(domain));
    reload();
  }, [project, domain, reload]);

  /** Uloží `next` nad jeho revizí; vrací true po úspěchu (model pak nese novou revizi z backendu). */
  const save = useCallback(async (next: StudioModel): Promise<boolean> => {
    const ticket = scope.current;
    setStatus("saving");
    const result = await saveStudioModel(project, domain, next);
    if (ticket !== scope.current) return false;
    if (result.kind === "saved") { setModel(result.model); setStatus("ready"); setMessage(""); return true; }
    setModel(next);
    setStatus(result.kind);
    setMessage(result.message);
    return false;
  }, [project, domain]);

  return { model, setModel, status, message, reload, save };
}
