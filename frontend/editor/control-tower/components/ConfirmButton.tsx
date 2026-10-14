// Tlačítko nevratného potvrzení ve frontě: dvojí klik s pamětí rozsahu (natažení na 8 s, pojistka 500 ms
// proti dvojkliku, opakovaný keydown nic nedělá), během ukládání „ukládám…“, výsledek a chyby jako
// stavová hláška. Stav tlačítka je jen jeho vlastní UI; potvrzení (a sdílený zámek) dělá rodič přes `action`.
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { ARM_MS, confirmLabel, confirmStep, idleConfirm, type ConfirmEvent, type ConfirmState } from "../logic/inbox-actions";

type Props = {
  label: string;
  /** Text nataženého stavu s rozsahem („Opravdu uzavřít „X“?“). */
  armed: string;
  /** Id karet, které tlačítko uzavře; při změně se natažení zruší. */
  scope: string[];
  /** Rozsah se kříží s právě potvrzovanými kartami (sdílený zámek). */
  locked: boolean;
  /** Potvrdí rozsah; vrátí hlášku (prázdná = nic hlásit) a zda něco selhalo. */
  action: (scope: string[]) => Promise<{ message: string; failed: boolean }>;
};

export default function ConfirmButton({ label, armed, scope, locked, action }: Props) {
  const [state, setState] = useState<ConfirmState>(idleConfirm);
  const latest = useRef(state);
  latest.current = state;
  const describedBy = useId();
  const scopeKey = scope.join("\n");
  const apply = (event: ConfirmEvent) => {
    const next = confirmStep(latest.current, Date.now(), event);
    latest.current = next.state;
    setState(next.state);
    return next.run;
  };
  useEffect(() => { apply({ type: "scope", scope }); }, [scopeKey]);
  useEffect(() => {
    if (state.kind !== "armed") return;
    const timer = setTimeout(() => apply({ type: "tick" }), ARM_MS + 50);
    return () => clearTimeout(timer);
  }, [state]);
  async function click() {
    const run = apply({ type: "click", scope });
    if (!run) return;
    try {
      const result = await action(run);
      apply({ type: "result", ...result });
    } catch (error) {
      apply({ type: "failure", message: String(error) });
    }
  }
  // Držená klávesa (Enter/mezerník) by tlačítko natáhla a hned potvrdila; opakování se ignoruje.
  const onKeyDown = (event: KeyboardEvent) => { if (event.repeat) event.preventDefault(); };
  const isArmed = state.kind === "armed";
  const message = state.kind === "error" || state.kind === "done" ? state.message : "";
  return (
    <span className="tower-inbox__confirm">
      <button type="button" disabled={state.kind === "busy" || locked} onClick={() => void click()} onKeyDown={onKeyDown}
        className={"tower-inbox__action" + (isArmed ? " tower-inbox__action--armed" : "") + (state.kind === "busy" ? " tower-inbox__action--busy" : "")}
        title="Uzavře kartu; vrátit jde jen novým kolem." aria-describedby={describedBy}>
        {confirmLabel(state, label, armed)}
      </button>
      <span id={describedBy} className={"tower-inbox__hint" + (isArmed ? " tower-inbox__hint--armed" : "")} role="status">
        {isArmed ? "Nevratné: uzavřenou kartu otevře jen nové kolo. Klikni znovu do " + ARM_MS / 1000 + " s." : locked ? "Čeká, než doběhne jiné potvrzení." : ""}
      </span>
      {message && <span className={state.kind === "error" ? "tower-inbox__error" : "tower-inbox__result"} role="status">{message}</span>}
    </span>
  );
}
