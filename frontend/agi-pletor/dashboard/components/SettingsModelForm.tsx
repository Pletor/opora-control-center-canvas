import { useState } from "react";
import { putPletorLlm } from "@/agi-pletor/hud/logic/pletor-client";
import PletorLlmModelSelect from "@/agi-pletor/hud/components/PletorLlmModelSelect";
import PletorEffortSelect from "@/agi-pletor/hud/components/PletorEffortSelect";
import { CODEX_EFFORTS, keepEffort } from "@/agi-pletor/hud/logic/llm-settings";
import { modelProblem, savedNote, type ModelRow } from "../logic/settings-view";

type Props = { target: "claude" | "codex"; title: string; row: ModelRow; onSaved: () => void };

/** Jeden řádek „Modely LLM“: aktuální model, výběr nového ze seznamu, effort (u Codexu úroveň uvažování) a Uložit. Nedostupná sekce ukáže jen důvod. */
export default function SettingsModelForm({ target, title, row, onSaved }: Props) {
  const [model, setModel] = useState(row.model);
  const [reasoning, setReasoning] = useState<string>(row.reasoning ?? "");
  const [note, setNote] = useState<{ text: string; error: boolean } | null>(null);
  if (!row.available) return <section className="pletor-dashboard__setting" aria-label={title}><h3 className="pletor-dashboard__group-title">{title}</h3><p className="pletor-dashboard__note">{row.reason || "nedostupné"}</p></section>;
  const problem = modelProblem(model);
  const found = row.models.find((m) => m.id === model)?.reasoning ?? [];
  const levels = found.length ? found : CODEX_EFFORTS;
  const save = () => {
    putPletorLlm(target, { model, ...(target === "codex" ? { reasoning } : { effort: reasoning }) }).then(
      (backup) => { setNote({ text: savedNote(backup), error: false }); onSaved(); },
      (error: unknown) => setNote({ text: error instanceof Error ? error.message : "Uložení selhalo.", error: true }),
    );
  };
  return (
    <section className="pletor-dashboard__setting" aria-label={title}>
      <h3 className="pletor-dashboard__group-title">{title}</h3>
      <p className="pletor-dashboard__note">Teď: <b>{row.model || "výchozí"}</b></p>
      <div className="pletor-dashboard__tools">
        <PletorLlmModelSelect className="pletor-dashboard__input" label={`Model ${title}`} models={row.models} value={model}
          onChange={(id) => { setModel(id); setReasoning((now) => keepEffort(row.models.find((m) => m.id === id)?.reasoning ?? CODEX_EFFORTS, now)); setNote(null); }} />
        <PletorEffortSelect className="pletor-dashboard__input" label={`Effort ${title}`} levels={levels} value={reasoning} onChange={setReasoning} />
        <button type="button" className="pletor-dashboard__button" disabled={problem !== null} title={problem ?? undefined} onClick={save}>Uložit</button>
      </div>
      {note && <p className={note.error ? "pletor-dashboard__error" : "pletor-dashboard__note"} role={note.error ? "alert" : "status"}>{note.text}</p>}
    </section>
  );
}
