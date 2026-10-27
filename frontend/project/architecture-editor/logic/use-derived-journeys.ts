// Odvozené kroky cest zákazníka pro mapu domény (docs/architektura-pro-agenty.md §6). Čte je znovu, když se změní
// projekt nebo otisk grafu (`view.digest`): každé uložení mapy může cestu spojit nebo přerušit. Odpověď, kterou
// mezitím předběhl novější dotaz, se zahodí. Chyba čtení cesty jen skryje: seznam cest zůstává použitelný bez nich.
// Dílky data dostanou od ArchitectureEditor.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { derivedJourneysUrl, normalizeDerivedJourneys, type DerivedJourney } from "../domain-map/logic/derived-journeys";

export function useDerivedJourneys(project: string, digest: string | undefined): DerivedJourney[] | null {
  const [journeys, setJourneys] = useState<DerivedJourney[] | null>(null);
  useEffect(() => {
    if (!project || !digest) return;
    let current = true;
    api<unknown>(derivedJourneysUrl(project))
      .then((raw) => { if (current) setJourneys(normalizeDerivedJourneys(raw)); })
      .catch(() => { if (current) setJourneys(null); });
    return () => { current = false; };
  }, [project, digest]);
  return journeys;
}
