// Uzavření karty: stav done, poznámka a dvě tlačítka. Agent smí uzavření jen navrhnout, potvrzuje člověk.
// Dílek nic neukládá; výsledek bublá nahoru přes onDone a zapisuje rodič (App) přes desktop.mutate(setDone).
import { useState } from "react";
import type { NodeDone } from "@/shared/desktop-state/logic/types";
import "@/editor/node-detail/done/styles/done-control.css";

export default function DoneControl({
  done,
  readOnly,
  busy,
  onDone,
}: {
  done: NodeDone;
  readOnly: boolean;
  busy: boolean;
  onDone: (patch: Partial<NodeDone>) => void;
}) {
  const [note, setNote] = useState(done.note);
  const proposed = done.by === "agent" && !done.confirmed;
  const stateLabel = done.confirmed ? "uzavřeno" : proposed ? "navrženo agentem" : "otevřeno";
  return (
    <div className="done-control" data-testid="done-control">
      <p className={"done-control__state done-control__state--" + (done.confirmed ? "closed" : proposed ? "proposed" : "open")}>
        <span className="done-control__mark" aria-hidden="true">{done.confirmed ? "🔒" : proposed ? "⌛" : "○"}</span>
        Stav karty: <b>{stateLabel}</b>
        {done.at && <span className="done-control__stamp"> · {done.at}</span>}
      </p>
      <p className="done-control__note">
        {done.confirmed
          ? "Uzavřená karta má bloky i porty jen ke čtení. Do hloubky se jít dál smí a vazba „další krok“ vede na další uzel."
          : proposed
            ? "Agent navrhl, že je hotovo. Potvrzení je na člověku; do té doby zůstává karta otevřená."
            : "Uzavřete kartu, až je práce doložená. Barva karty není důkaz; ten dávají testy, review a merge."}
      </p>
      <label className="done-control__field">
        Poznámka k uzavření
        <textarea
          className="done-control__input"
          aria-label="Poznámka k uzavření karty"
          rows={3}
          maxLength={2000}
          readOnly={readOnly}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      <div className="done-control__actions">
        <button
          type="button"
          className="done-control__button primary"
          data-testid="done-close"
          disabled={readOnly || busy || done.confirmed}
          onClick={() => onDone({ confirmed: true, by: "human", note })}
        >
          Uzavřít kartu
        </button>
        <button
          type="button"
          className="done-control__button"
          data-testid="done-reopen"
          disabled={readOnly || busy || (!done.confirmed && !proposed)}
          onClick={() => onDone({ confirmed: false, by: "human", note })}
        >
          Znovu otevřít
        </button>
      </div>
    </div>
  );
}
