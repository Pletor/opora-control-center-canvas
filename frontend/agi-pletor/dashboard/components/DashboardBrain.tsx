import { useEffect, useState } from "react";
import { CLAUDE_BRAIN, fetchPletorLlm, fetchPletorState, setPletorBrain, type PletorBrain } from "@/agi-pletor/hud/logic/pletor-client";
import type { PletorLlm } from "@/agi-pletor/hud/logic/llm-settings";
import PletorSettingsLlm from "@/agi-pletor/hud/components/PletorSettingsLlm";

const message = (error: unknown) => (error instanceof Error ? error.message : "Načtení selhalo.");

/**
 * Mozek a LLM: malý přepínač Claude / Ollama (`POST /api/pletor/brain`, stejně jako v nastavení HUD) a pod ním
 * přehled LLM na tomto počítači (`PletorSettingsLlm`, `GET /api/pletor/llm`, načte se při otevření části).
 */
export default function DashboardBrain({ project, workspace }: { project: string; workspace: string }) {
  const [brain, setBrain] = useState<PletorBrain>(CLAUDE_BRAIN);
  const [note, setNote] = useState("");
  const [llm, setLlm] = useState<{ data: PletorLlm | null; loading: boolean; error: string | null }>({ data: null, loading: true, error: null });
  const loadLlm = () => {
    setLlm((now) => ({ ...now, loading: true, error: null }));
    fetchPletorLlm().then((data) => setLlm({ data, loading: false, error: null }), (error: unknown) => setLlm((now) => ({ ...now, loading: false, error: message(error) })));
  };
  useEffect(() => {
    loadLlm();
    fetchPletorState(project, workspace).then((state) => setBrain(state.brain), (error: unknown) => setNote(message(error)));
  }, [project, workspace]);
  const choose = (next: PletorBrain["brain"]) => {
    setPletorBrain(next).then((result) => { setBrain(result.brain); setNote(result.ok ? "" : result.reply); }, (error: unknown) => setNote(message(error)));
  };
  const local = brain.brain === "ollama" ? brain.model : brain.available[0] ?? null;
  return (
    <>
      <div className="pletor-dashboard__switch" role="group" aria-label="Mozek Pletora">
        <button type="button" className="pletor-dashboard__choice" aria-pressed={brain.brain === "claude"} onClick={() => choose("claude")}>Claude (předplatné)</button>
        <button type="button" className="pletor-dashboard__choice" aria-pressed={brain.brain === "ollama"} disabled={!local}
          title={local ? undefined : "Ollama nenabízí žádný model"} onClick={() => choose("ollama")}>Lokální (Ollama · {local ?? "bez modelu"})</button>
      </div>
      {note && <p className="pletor-dashboard__error" role="alert">{note}</p>}
      <PletorSettingsLlm llm={llm.data} loading={llm.loading} error={llm.error} onRefresh={loadLlm} />
    </>
  );
}
