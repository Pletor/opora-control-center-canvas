// Data panelu Komponenty: registr Brainu (Skills, Tools) a přehled čtení dokumentace Harness projektu. Obojí se čte
// jednou při otevření přehledu domén a při změně projektu nebo prostoru; nic se nezapisuje. Chyba čtení zůstane větou
// u karty, panel zůstává použitelný. Dílky data dostanou od ArchitectureLanding.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { parseBrainArtifacts, parseHarness, type ShelfData } from "./component-shelf";

const LOADING: ShelfData = { brain: { data: null, error: "" }, harness: { data: null, error: "" } };
const reason = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export function useComponentShelf(project: string, workspace: string): ShelfData {
  const [data, setData] = useState<ShelfData>(LOADING);
  useEffect(() => {
    let current = true;
    setData(LOADING);
    const put = (patch: Partial<ShelfData>) => { if (current) setData((old) => ({ ...old, ...patch })); };
    api<unknown>("/api/brain-registry/artifacts")
      .then((raw) => put({ brain: { data: parseBrainArtifacts(raw), error: "" } }))
      .catch((cause) => put({ brain: { data: null, error: reason(cause) } }));
    if (project && workspace) api<unknown>("/api/oporahub/harness-documentation?" + new URLSearchParams({ project, workspace }))
      .then((raw) => put({ harness: { data: parseHarness(raw), error: "" } }))
      .catch((cause) => put({ harness: { data: null, error: reason(cause) } }));
    else put({ harness: { data: null, error: "Projekt není otevřený." } });
    return () => { current = false; };
  }, [project, workspace]);
  return data;
}
