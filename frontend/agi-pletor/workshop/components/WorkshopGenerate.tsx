import { useId, useState, type FormEvent } from "react";
import { TOOL_NAME_RE } from "../logic/workshop-state";

type Props = { busy: boolean; blocked: boolean; onGenerate: (name: string, intent: string) => void };

/** Blok „Vygenerovat“ pod seznamy: název a věta o tom, co má funkce dělat; model napíše kód i případy a Dílna je změří. */
export default function WorkshopGenerate({ busy, blocked, onGenerate }: Props) {
  const [name, setName] = useState("");
  const [intent, setIntent] = useState("");
  const nameId = useId(), intentId = useId();
  const ready = TOOL_NAME_RE.test(name) && intent.trim() !== "";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!ready || blocked) return;
    onGenerate(name, intent.trim());
  };
  return (
    <form className="pletor-workshop__generate" onSubmit={submit} aria-label="Vygenerovat funkci">
      <h3 className="pletor-workshop__list-title">Vygenerovat</h3>
      <label className="pletor-workshop__new-label" htmlFor={nameId}>Název funkce</label>
      <input id={nameId} className="pletor-workshop__new-input" value={name} placeholder="nazev_funkce" spellCheck={false}
        aria-invalid={name !== "" && !TOOL_NAME_RE.test(name)} onChange={(event) => setName(event.target.value)} />
      <label className="pletor-workshop__new-label" htmlFor={intentId}>Co má funkce dělat</label>
      <textarea id={intentId} className="pletor-workshop__generate-intent" value={intent} onChange={(event) => setIntent(event.target.value)} />
      <button type="submit" className="pletor-workshop__button" disabled={!ready || busy || blocked}
        title={blocked ? "Nejdřív ulož rozepsanou funkci" : undefined}>{busy ? "Model píše…" : "Vygenerovat a změřit"}</button>
    </form>
  );
}
