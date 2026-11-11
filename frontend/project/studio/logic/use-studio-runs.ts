// Cesty zákazníka s posledním ověřením (`lastRun`) pro Studio: stejný dotaz jako mapa domény
// (`GET /api/project-architecture/journeys`), ale čte se i bez změny mapy, protože nový doklad cesty otisk grafu
// nemění. Sdílený poller (`usePolling`): znovu při změně projektu nebo otisku, na „Obnovit“ a každých 15 s (3 s, když
// některá cesta právě běží, `runsPollMs`), jen když je dokument vidět (pohyb Skutečnosti ukazuje, co právě běží,
// prošlo nebo spadlo). Chyba čtení nechá poslední známý stav;
// odpověď předběhnutá novějším dotazem nebo jiným projektem se zahodí. Jen čte.
import { useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { derivedJourneysUrl, normalizeDerivedJourneys, runsPollMs, type DerivedJourney } from "@/project/architecture-editor/domain-site/logic/derived-journeys";

export function useStudioRuns(project: string, digest: string | undefined): { journeys: DerivedJourney[] | null; refresh: () => void } {
  const [journeys, setJourneys] = useState<DerivedJourney[] | null>(null);
  const asked = useRef({ project, ticket: 0 });
  asked.current.project = project;
  // Poslední přečtené cesty pro interval: zapisují se hned v dotazu, ne až po renderu, aby další kolo znalo běh.
  const latest = useRef<DerivedJourney[] | null>(null);
  const poll = usePolling(async () => {
    const ticket = ++asked.current.ticket;
    const forProject = project;
    try {
      const next = normalizeDerivedJourneys(await api<unknown>(derivedJourneysUrl(forProject)));
      if (ticket === asked.current.ticket && asked.current.project === forProject) { latest.current = next; setJourneys(next); }
    } catch { /* poslední známý stav zůstává */ }
  }, { intervalMs: () => runsPollMs(latest.current), enabled: !!project && !!digest, refreshKeys: [project, digest] });
  return { journeys, refresh: () => { void poll.refresh(); } };
}
