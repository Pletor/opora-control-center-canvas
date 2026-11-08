import "../styles/pletor-settings.css";
import { useEffect, useRef, useState } from "react";
import { fetchPletorLlm, type PletorBrain, type PletorBrainKind } from "../logic/pletor-client";
import type { PletorLlm } from "../logic/llm-settings";
import { readListenPrefs, writeListenPrefs } from "../logic/listen-prefs";
import type { usePletorVoice } from "../logic/use-pletor-voice";
import PletorBrainPicker from "./PletorBrainPicker";
import PletorListenSwitch from "./PletorListenSwitch";
import PletorSettingsLlm from "./PletorSettingsLlm";
import PletorSettingsVoices from "./PletorSettingsVoices";
import PletorWorkshop from "@/agi-pletor/workshop/components/PletorWorkshop";

type Tab = "brain" | "voice" | "llm" | "workshop";
const TABS: [Tab, string][] = [["brain", "Mozek a čtení"], ["voice", "Hlas"], ["llm", "LLM"], ["workshop", "Dílna"]];

type Props = {
  voice: ReturnType<typeof usePletorVoice>; brain: PletorBrain; onBrain: (brain: PletorBrainKind, model?: string, effort?: string) => void; onClose: () => void;
};

/**
 * Nastavení Pletora za ozubeným kolem ve čtyřech záložkách: mozek (Claude / Codex / Ollama) s přepínači čtení a poslechu, hlas
 * (tabulka hlasů), LLM na tomto počítači jen ke čtení (`GET /api/pletor/llm`, načte se při prvním otevření záložky)
 * a Dílna, která se otevře jako celoobrazovková vrstva (`PletorWorkshop`) a po zavření vrátí focus na „Otevřít dílnu“.
 * Volby se ukládají jako dosud jednou pro aplikaci (voice-prefs, listen-prefs); mozek přepíná server (`onBrain`).
 * Zavře ho Esc, klik mimo nebo znovu kolo; HUD mezitím Esc nebere (PletorHud `settingsOpen`).
 */
export default function PletorSettingsPanel({ voice, brain, onBrain, onClose }: Props) {
  const ref = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  const [wakeOnly, setWakeOnly] = useState(() => readListenPrefs().wakeOnly);
  const [tab, setTab] = useState<Tab>("brain");
  const [llm, setLlm] = useState<{ data: PletorLlm | null; loading: boolean; error: string | null }>({ data: null, loading: false, error: null });

  const loadLlm = () => {
    setLlm((now) => ({ ...now, loading: true, error: null }));
    fetchPletorLlm().then((data) => setLlm({ data, loading: false, error: null }),
      (error: unknown) => setLlm((now) => ({ ...now, loading: false, error: error instanceof Error ? error.message : "Načtení selhalo." })));
  };
  // Dílna potřebuje místo na dva editory, proto se z malého panelu otevře jako celoobrazovková vrstva.
  const [workshop, setWorkshop] = useState(false);
  const workshopOpen = useRef(false);
  workshopOpen.current = workshop;
  const workshopButton = useRef<HTMLButtonElement>(null);
  const closeWorkshop = () => { setWorkshop(false); requestAnimationFrame(() => workshopButton.current?.focus()); };
  const openTab = (next: Tab) => {
    setTab(next);
    if ((next === "llm" || next === "brain") && !llm.data && !llm.loading) loadLlm();
    if (next === "workshop") setWorkshop(true);
  };

  useEffect(() => {
    loadLlm(); // záložka Mozek je první a modely Codexu potřebuje hned; jednou při otevření
    ref.current?.focus();
    // Otevřená Dílna si Esc bere sama (zavře jen sebe).
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape" && !workshopOpen.current) { event.preventDefault(); close.current(); } };
    const onDown = (event: PointerEvent) => {
      const target = event.target as Element;
      if (!ref.current?.contains(target) && !target.closest?.("[data-pletor-settings-toggle]")) close.current();
    };
    window.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown, true);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onDown, true); };
  }, []);

  // Poloha popupu se ukládá zvlášť (PletorListener); tady se mění jen „jen na oslovení“.
  const saveWake = (on: boolean) => { setWakeOnly(on); writeListenPrefs({ ...readListenPrefs(), wakeOnly: on }); };

  return (
    <section ref={ref} className="pletor-settings" role="dialog" aria-label="Nastavení Pletora" tabIndex={-1}>
      <header className="pletor-settings__head">
        <strong className="pletor-settings__title">Nastavení Pletora</strong>
        <button type="button" className="pletor-settings__close" aria-label="Zavřít nastavení" onClick={onClose}>×</button>
      </header>

      <div className="pletor-settings__tabs" role="tablist" aria-label="Části nastavení">
        {TABS.map(([id, label]) => (
          <button key={id} type="button" role="tab" className="pletor-settings__tab" aria-selected={tab === id} onClick={() => openTab(id)}>{label}</button>
        ))}
      </div>

      {tab === "brain" && <div className="pletor-settings__pane" role="tabpanel" aria-label="Mozek a čtení">
        <h3 className="pletor-settings__section">Mozek</h3>
        <PletorBrainPicker brain={brain} claude={llm.data?.claude.models ?? []} codex={llm.data?.codex.models ?? []} onChoose={onBrain} />

        <h3 className="pletor-settings__section">Čtení a poslech</h3>
        <div className="pletor-settings__switches">
          <PletorListenSwitch tone="small" label="Hlas" title="Odpovědi čte nahlas i na psané zprávy" on={voice.prefs.voice}
            onChange={(on) => voice.setPrefs({ voice: on })} />
          {voice.supported && (
            <PletorListenSwitch tone="small" label="Konverzace" title="Po odpovědi Pletor znovu poslouchá" on={voice.prefs.conversation}
              onChange={(on) => voice.setPrefs({ conversation: on })} />
          )}
          <PletorListenSwitch tone="small" label="Přerušení hlasem" title="V Poslechu řeč člověka utne čtení odpovědi; bez sluchátek vypni" on={voice.prefs.bargeIn}
            onChange={(on) => voice.setPrefs({ bargeIn: on })} />
          <PletorListenSwitch tone="small" label="Jen na oslovení" title="Reaguje jen věta s oslovením Pletore / Jarvisi" on={wakeOnly} onChange={saveWake} />
        </div>
      </div>}

      {tab === "voice" && <div className="pletor-settings__pane" role="tabpanel" aria-label="Hlas">
        <PletorSettingsVoices voices={voice.voices} chosen={voice.chosen} onChoose={(id) => voice.setPrefs({ ttsVoice: id })} onTry={voice.tryVoice} />
      </div>}

      {tab === "llm" && <div className="pletor-settings__pane" role="tabpanel" aria-label="LLM">
        <PletorSettingsLlm llm={llm.data} loading={llm.loading} error={llm.error} onRefresh={loadLlm} />
      </div>}

      {tab === "workshop" && <div className="pletor-settings__pane" role="tabpanel" aria-label="Dílna">
        <p className="pletor-settings__hint">Skilly a měřitelné funkce Pletora ve dvou editorech vedle sebe.</p>
        <button ref={workshopButton} type="button" className="pletor-settings__brain" onClick={() => setWorkshop(true)}>Otevřít dílnu</button>
      </div>}
      {workshop && <PletorWorkshop onClose={closeWorkshop} />}
    </section>
  );
}
