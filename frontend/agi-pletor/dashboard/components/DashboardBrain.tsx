import { useEffect, useState } from "react";
import { CLAUDE_BRAIN, fetchPletorLlm, fetchPletorState, setPletorBrain, type PletorBrain, type PletorBrainKind } from "@/agi-pletor/hud/logic/pletor-client";
import type { PletorLlm } from "@/agi-pletor/hud/logic/llm-settings";
import PletorBrainPicker from "@/agi-pletor/hud/components/PletorBrainPicker";
import HeartModelPicker from "./HeartModelPicker";
import PletorSettingsLlm from "@/agi-pletor/hud/components/PletorSettingsLlm";

const message = (error: unknown) => (error instanceof Error ? error.message : "Načtení selhalo.");

/**
 * Mozek a LLM ve třech sekcích: Pletor (volba mozku Claude / Codex / Ollama, `PletorBrainPicker`, `POST /api/pletor/brain`), Srdce (model a poradce,
 * `HeartModelPicker`) a Tento počítač (společné CLI a účty, `PletorSettingsLlm`, `GET /api/pletor/llm`, načte se při otevření části).
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
  const choose = (next: PletorBrainKind, model?: string, effort?: string) => {
    setPletorBrain(next, model, effort).then((result) => { setBrain(result.brain); setNote(result.ok ? "" : result.reply); }, (error: unknown) => setNote(message(error)));
  };
  return (
    <>
      <section className="pletor-dashboard__section">
        <h3 className="pletor-dashboard__section-title">Pletor</h3>
        <p className="pletor-dashboard__note">Mluví s tebou a zadává srdci, na plátno nepíše.</p>
        <PletorBrainPicker brain={brain} claude={llm.data?.claude.models ?? []} codex={llm.data?.codex.models ?? []} onChoose={choose} />
        {note && <p className="pletor-dashboard__error" role="alert">{note}</p>}
      </section>
      <section className="pletor-dashboard__section">
        <h3 className="pletor-dashboard__section-title">Srdce</h3>
        <p className="pletor-dashboard__note">Jediný zapisovatel plátna, pracuje v dávkách, Claude Code s poradcem.</p>
        <HeartModelPicker />
      </section>
      <section className="pletor-dashboard__section">
        <h3 className="pletor-dashboard__section-title">Tento počítač</h3>
        <PletorSettingsLlm llm={llm.data} loading={llm.loading} error={llm.error} onRefresh={loadLlm} />
      </section>
    </>
  );
}
