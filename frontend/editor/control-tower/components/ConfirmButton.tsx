// Tlačítko nevratného potvrzení ve frontě: dvojí klik (natažení na 4 s), během ukládání „ukládám…“,
// chyba jako text vedle. Stav tlačítka je jen jeho vlastní UI; data mění rodič přes `action`.
import { useEffect, useState } from "react";
import { ARM_MS, confirmLabel, confirmStep, idleConfirm, type ConfirmEvent, type ConfirmState } from "../logic/inbox-actions";

type Props = { label: string; action: () => Promise<boolean | void> };

export default function ConfirmButton({ label, action }: Props) {
  const [state, setState] = useState<ConfirmState>(idleConfirm);
  const step = (event?: ConfirmEvent) => {
    const next = confirmStep(state, Date.now(), event);
    setState(next.state);
    return next.run;
  };
  useEffect(() => {
    if (state.kind !== "armed") return;
    const timer = setTimeout(() => setState((s) => confirmStep(s, Date.now(), { type: "tick" }).state), ARM_MS + 50);
    return () => clearTimeout(timer);
  }, [state]);
  async function click() {
    if (!step()) return;
    try {
      const ok = await action();
      setState((s) => confirmStep(s, Date.now(), ok === false ? { type: "failure", message: "" } : { type: "success" }).state);
    } catch (error) {
      setState((s) => confirmStep(s, Date.now(), { type: "failure", message: String(error) }).state);
    }
  }
  return (
    <span className="tower-inbox__confirm">
      <button type="button" disabled={state.kind === "busy"} onClick={() => void click()}
        className={"tower-inbox__action" + (state.kind === "armed" ? " tower-inbox__action--armed" : "") + (state.kind === "busy" ? " tower-inbox__action--busy" : "")}
        title="Uzavře kartu; vrátit jde jen novým kolem.">
        {confirmLabel(state, label)}
      </button>
      {state.kind === "error" && <span className="tower-inbox__error" role="alert">{state.message}</span>}
    </span>
  );
}
