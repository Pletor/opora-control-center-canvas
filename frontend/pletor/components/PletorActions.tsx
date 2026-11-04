import { actionLabel, type PletorAction } from "../logic/pletor-client";

/** Chipy akcí, které Pletor po poslední odpovědi provedl (zpráva srdci, zápis do Schránky, selhání). */
export default function PletorActions({ actions }: { actions: PletorAction[] }) {
  if (actions.length === 0) return null;
  return (
    <ul className="pletor__actions" aria-label="Provedené akce">
      {actions.map((action, index) => {
        const label = actionLabel(action);
        return (
          <li key={index} className={"pletor__action" + (label.ok ? "" : " pletor__action--failed")} title={action.text}>{label.text}</li>
        );
      })}
    </ul>
  );
}
