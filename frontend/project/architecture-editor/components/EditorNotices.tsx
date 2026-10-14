import type { EditLock } from "../logic/edit-locks";
import type { ViewConflict } from "../view-conflicts/logic/view-conflicts";
import DomainLockNote from "../landing/components/DomainLockNote";
import ConflictBanner from "../view-conflicts/components/ConflictBanner";

/** Řádky pod hlavičkou editoru: chyba poslední akce, proč je úprava zakázaná a rozdíly proti architektuře. */
export default function EditorNotices({ error, lock, conflicts }: { error: string; lock: EditLock; conflicts: ViewConflict[] }) {
  return <>
    {error && <div className="ae-message" role="alert">{error}</div>}
    <DomainLockNote lock={lock}/>
    <ConflictBanner conflicts={conflicts}/>
  </>;
}
