// Cesty zákazníka s posledním ověřením (`lastRun`) pro Studio: stejný dotaz jako mapa domény
// (`GET /api/project-architecture/journeys`), ale čte se i bez změny mapy, protože nový doklad cesty otisk grafu
// nemění. Sdílený poller (`usePolling`): znovu při změně projektu nebo otisku, na „Obnovit“ a každých 15 s, jen když
// je dokument vidět (pohyb Skutečnosti ukazuje, co právě prošlo nebo spadlo). Chyba čtení nechá poslední známý stav;
// odpověď předběhnutá novějším dotazem nebo jiným projektem se zahodí. Jen čte.
import { useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { derivedJourneysUrl, normalizeDerivedJourneys, type DerivedJourney } from "@/project/architecture-editor/domain-map/logic/derived-journeys";

export const RUNS_POLL_MS = 15_000;

export function useStudioRuns(project: string, digest: string | undefined): { journeys: DerivedJourney[] | null; refresh: () => void } {
  const [journeys, setJourneys] = useState<DerivedJourney[] | null>(null);
  const asked = useRef({ project, ticket: 0 });
  asked.current.project = project;
  const poll = usePolling(async () => {
    const ticket = ++asked.current.ticket;
    const forProject = project;
    try {
      const next = normalizeDerivedJourneys(await api<unknown>(derivedJourneysUrl(forProject)));
      if (ticket === asked.current.ticket && asked.current.project === forProject) setJourneys(next);
    } catch { /* poslední známý stav zůstává */ }
  }, { intervalMs: RUNS_POLL_MS, enabled: !!project && !!digest, refreshKeys: [project, digest] });
  return { journeys, refresh: () => { void poll.refresh(); } };
}
