/** Stav a uložení Správy webu vpravo v hlavičce: revize nebo „Neuložené změny“ a jediné tlačítko Uložit. */
export default function SiteSaveBar({ revision, dirty, saving, disabled, onSave }: {
  revision: number; dirty: boolean; saving: boolean; disabled: boolean; onSave: () => void;
}) {
  const status = saving ? "Ukládám…" : dirty ? "Neuložené změny" : revision ? `Uloženo · revize ${revision}` : "Zatím neuloženo";
  return <div className="site-admin__save">
    <span className={"site-admin__status" + (dirty ? " site-admin__status--dirty" : "")} role="status" data-testid="site-admin-status">{status}</span>
    <button type="button" className="primary" data-testid="site-admin-save" disabled={disabled || saving || !dirty} onClick={onSave}>Uložit</button>
  </div>;
}
