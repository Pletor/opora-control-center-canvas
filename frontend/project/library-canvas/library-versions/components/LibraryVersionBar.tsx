import type { FlowVersion } from "@/shared/flow-editor/logic/flow-types";
import { history, STATUS_LABEL, versionAction } from "../logic/library-versions";
import "../styles/library-versions.css";

type Props = {
  versions: FlowVersion[]; viewing: FlowVersion | null; dirty: boolean; busy: boolean; readOnly: boolean;
  onView: (id: string) => void; onSaveDraft: () => void; onDiscard: () => void; onActivate: () => void; onRollback: () => void;
};
const ACTION = { activate: "Aktivovat", restore: "Vrátit na tuto verzi", rollback: "Návrat na předchozí" } as const;

/** Lišta verzí plátna toku: zobrazená verze s výběrem z historie, neuložená úprava jde uložit jako nový draft, draft
 * jde aktivovat a k dřívější verzi se jde vrátit. Bez schválení: kdo smí do části knihovny psát, ten aktivuje. */
export default function LibraryVersionBar({ versions, viewing, dirty, busy, readOnly, onView, onSaveDraft, onDiscard, onActivate, onRollback }: Props) {
  const action = dirty || readOnly ? null : versionAction(versions, viewing);
  return <div className="library-versions" data-testid="library-versions">
    <label className="library-versions__history">Verze
      <select className="library-versions__select" disabled={busy || !versions.length} value={viewing?.id ?? ""} data-testid="library-versions-history"
        onChange={(event) => onView(event.target.value)}>
        {!versions.length && <option value="">zatím žádná, první uložení ji založí</option>}
        {history(versions).map((version) => <option key={version.id} value={version.id}>v{version.n} · {STATUS_LABEL[version.status]} · {new Date(version.created_at).toLocaleString("cs-CZ")}</option>)}
      </select>
    </label>
    {viewing && <span className={`library-versions__status library-versions__status--${viewing.status}`}>{STATUS_LABEL[viewing.status]}</span>}
    <span className="library-versions__actions">
      {dirty && <>
        <span className="library-versions__dirty">neuložená úprava</span>
        <button type="button" className="library-versions__button library-versions__button--primary" disabled={busy} data-testid="library-save-draft" onClick={onSaveDraft}>Uložit draft</button>
        <button type="button" className="library-versions__button" disabled={busy} onClick={onDiscard}>Zahodit</button>
      </>}
      {action && <button type="button" className="library-versions__button" disabled={busy} data-testid={`library-version-${action}`}
        onClick={action === "rollback" ? onRollback : onActivate}>{ACTION[action]}</button>}
    </span>
  </div>;
}
