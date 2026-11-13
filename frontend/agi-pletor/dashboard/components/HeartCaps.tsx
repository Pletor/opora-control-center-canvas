import { useEffect, useState } from "react";
import { CAP_FIELDS, capProblem, capsChanges, fetchHeartCaps, putHeartCaps, type Caps, type CapKey } from "../logic/heart-caps";

const message = (error: unknown) => (error instanceof Error ? error.message : "Uložení selhalo.");

/** Stropy srdce (`GET/PUT /api/pletor/heart/caps`): člověk tu určuje, kolik práce si srdce smí vzít; odešlou se jen změněná pole. */
export default function HeartCaps() {
  const [caps, setCaps] = useState<Caps | null>(null);
  const [draft, setDraft] = useState<Record<CapKey, string>>({ per_hour: "", per_project: "", rate_sleep_seconds: "" });
  const [error, setError] = useState("");
  const apply = (next: Caps) => { setCaps(next); setDraft({ per_hour: String(next.values.per_hour), per_project: String(next.values.per_project), rate_sleep_seconds: String(next.values.rate_sleep_seconds) }); setError(""); };
  useEffect(() => { fetchHeartCaps().then(apply, (e: unknown) => setError(message(e))); }, []);
  const problems = caps ? CAP_FIELDS.map(({ key }) => capProblem(caps, key, Number(draft[key]))) : [];
  const save = () => {
    if (!caps) return;
    const numbers = Object.fromEntries(CAP_FIELDS.map(({ key }) => [key, Number(draft[key])])) as Record<CapKey, number>;
    putHeartCaps(capsChanges(caps, numbers)).then(apply, (e: unknown) => setError(message(e)));
  };
  return (
    <section className="heart-caps" aria-label="Stropy srdce">
      <h2 className="pletor-dashboard__group-title">Stropy srdce</h2>
      {caps && (
        <>
          {CAP_FIELDS.map(({ key, label }, i) => (
            <label key={key} className="heart-caps__field">{label}
              <input type="number" className="pletor-dashboard__input" value={draft[key]} min={caps.bounds[key][0]} max={caps.bounds[key][1]}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
              {problems[i] && <span className="heart-caps__problem">{problems[i]}</span>}
            </label>
          ))}
          <p className="pletor-dashboard__note">Zpráva člověka strop za hodinu obchází. Platí pro všechny projekty.</p>
          <button type="button" className="pletor-dashboard__button" disabled={problems.some(Boolean)} onClick={save}>Uložit</button>
        </>
      )}
      {error && <p className="pletor-dashboard__error" role="alert">{error}</p>}
    </section>
  );
}
