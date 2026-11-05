import { useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { fetchPletorState, type PletorState } from "@/agi-pletor/hud/logic/pletor-client";
import { readVoicePrefs } from "@/agi-pletor/hud/logic/voice-prefs";
import { overviewCards, voiceName } from "../logic/overview-cards";
import { useVoiceList } from "../logic/use-voice-list";

const POLL_MS = 5000;

/**
 * Přehled: jedna obrazovka „jak se organismu daří“ z pěti karet (mozek, srdce, eskalace, hlas, poslední zpráva).
 * Stav se čte z `GET /api/pletor/state` každých 5 s, dokud je část vidět (komponenta existuje jen v aktivní části).
 * Karty skládá `overviewCards`; tady je jen načtení a vykreslení.
 */
export default function DashboardOverview({ project, workspace }: { project: string; workspace: string }) {
  const [state, setState] = useState<PletorState | null>(null);
  const [error, setError] = useState("");
  const voices = useVoiceList();
  usePolling(() => fetchPletorState(project, workspace).then(
    (next) => { setState(next); setError(""); },
    (failure: unknown) => setError(failure instanceof Error ? failure.message : "Načtení selhalo."),
  ), { intervalMs: POLL_MS, enabled: !!project && !!workspace, refreshKeys: [project, workspace] });
  const cards = overviewCards(state, voices ? voiceName(readVoicePrefs().ttsVoice, voices) : "—");
  return (
    <>
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
      <div className="pletor-dashboard__cards">
        {cards.map((card) => (
          <section key={card.id} className="pletor-dashboard__card" aria-label={card.title}>
            <h2 className="pletor-dashboard__card-title">{card.title}</h2>
            <p className="pletor-dashboard__card-value">{card.value}</p>
            <p className="pletor-dashboard__card-note">{card.note}</p>
          </section>
        ))}
      </div>
    </>
  );
}
