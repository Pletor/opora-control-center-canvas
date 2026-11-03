// Stav záměrů stránek projektu: načte se při otevření a po každé změně grafu architektury (`digest`).
import { useEffect, useState } from "react";
import { loadPageIntents, type PageIntents } from "./page-intents";

export function usePageIntents(project: string, digest: string | undefined): PageIntents | null {
  const [intents, setIntents] = useState<PageIntents | null>(null);
  useEffect(() => {
    let alive = true;
    void loadPageIntents(project).then((next) => { if (alive) setIntents(next); });
    return () => { alive = false; };
  }, [project, digest]);
  return intents;
}
