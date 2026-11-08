import { useEffect, useState } from "react";
import PletorEffortSelect from "@/agi-pletor/hud/components/PletorEffortSelect";
import PletorLlmModelSelect from "@/agi-pletor/hud/components/PletorLlmModelSelect";
import { fetchHeartModel, putHeartModel, type HeartModel } from "../logic/heart-model";

const message = (error: unknown) => (error instanceof Error ? error.message : "Uložení selhalo.");

/** Model, effort a poradce srdce (`GET/PUT /api/pletor/heart/model`): změna se uloží hned a platí od další dávky srdce.
 *  Poradce effort nemá (Claude Code pro něj nemá přepínač). */
export default function HeartModelPicker() {
  const [heart, setHeart] = useState<HeartModel | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchHeartModel().then(setHeart, (e: unknown) => setError(message(e))); }, []);
  const save = (model: string, advisor: string, effort: string) => putHeartModel(model, advisor, effort).then((next) => { setHeart(next); setError(""); }, (e: unknown) => setError(message(e)));
  return (
    <div className="heart-model">
      {heart && (
        <>
          <label className="heart-model__field">Model
            <PletorLlmModelSelect models={heart.models} value={heart.model} label="Model srdce" onChange={(id) => save(id, heart.advisor, heart.effort ?? "")} />
          </label>
          <label className="heart-model__field">Effort
            <PletorEffortSelect levels={heart.efforts} value={heart.effort ?? ""} label="Effort srdce" onChange={(level) => save(heart.model, heart.advisor, level)} />
          </label>
          <label className="heart-model__field">Poradce
            <PletorLlmModelSelect models={heart.models} value={heart.advisor} label="Poradce srdce" onChange={(id) => save(heart.model, id, heart.effort ?? "")} />
          </label>
        </>
      )}
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
    </div>
  );
}
