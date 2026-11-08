import type { PletorAction } from "../logic/linie-actions";
import LinieUntested from "./LinieUntested";

type Props = { actions: PletorAction[]; note: string; onNote: (note: string) => void; onAct: (id: string) => void };

/**
 * Akce kuličky jako tlačítka (zakázané šedé s důvodem v `title`), sdílené panelem Pletora i záložkou Git. U přijetí
 * stojí pole poznámky: je to záznam rozhodnutí člověka, smí zůstat prázdné. „Přijmout bez zkoušky“ je odkaz s potvrzením.
 */
export default function LinieActions({ actions, note, onNote, onAct }: Props) {
  if (!actions.length) return null;
  return (
    <>
      {actions.some((action) => action.id === "accept" || action.id === "accept_untested") && (
        <input className="pletor-dashboard__input" aria-label="Poznámka k přijetí" placeholder="poznámka k přijetí (nepovinná)" value={note}
          onChange={(event) => onNote(event.target.value)} />
      )}
      <span className="pletor-dashboard__tools pletor-dashboard__linie-acts">
        {actions.map((action) => action.id === "accept_untested" ? <LinieUntested key={action.id} disabled={!action.enabled} onConfirm={() => onAct(action.id)} /> : (
          <button key={action.id} type="button" className="pletor-dashboard__button" disabled={!action.enabled} title={action.why || undefined}
            onClick={() => onAct(action.id)}>{action.label}</button>
        ))}
      </span>
    </>
  );
}
