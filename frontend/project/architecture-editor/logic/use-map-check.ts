// Kontrola mapy (díry mapy, docs/architektura-pro-agenty.md §5) pro plátno 2. Čte ji znovu, když se změní projekt nebo
// otisk grafu (`view.digest`): každé uložení mapy může díru zacelit nebo novou otevřít. Odpověď, kterou mezitím předběhl
// novější dotaz, se zahodí. Chyba čtení panel jen skryje (null): mapa zůstává použitelná bez něj.
// Čte se s `locate=1`: nálezy nesou `solverId`, podle kterého rozklad stránky páruje díry cest (§5.3).
// Dílky data dostanou od ArchitectureEditor.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { mapCheckUrl, normalizeMapCheck, type MapCheck } from "../domain-site/map-check/logic/map-check";

export function useMapCheck(project: string, digest: string | undefined): MapCheck | null {
  const [check, setCheck] = useState<MapCheck | null>(null);
  useEffect(() => {
    if (!project || !digest) return;
    let current = true;
    api<unknown>(mapCheckUrl(project, true))
      .then((raw) => { if (current) setCheck(normalizeMapCheck(raw)); })
      .catch(() => { if (current) setCheck(null); });
    return () => { current = false; };
  }, [project, digest]);
  return check;
}
