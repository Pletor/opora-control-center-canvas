import PageIcon from "../page-editor/components/PageIcon";

type Props = {
  crumbs: string[]; step: string; workspace: string; readOnly: boolean; editorId: string;
  back: { disabled: boolean; onClick: () => void } | null;
  exportDisabled: boolean; reloadDisabled: boolean; onExport: () => void; onReload: () => void; onCopyId: () => void;
};

/** Top bar of the architecture screen: where I am (environment / host / page) and what I can do here. */
export default function ArchitectureHeader(props: Props) {
  const { crumbs, step, workspace, readOnly, editorId, back } = props;
  return <header className="ae-header">
    {back && <button type="button" className="ae-header__back" data-testid="architecture-back" disabled={back.disabled} onClick={back.onClick}>← Zpět</button>}
    <div className="ae-header__brand">
      <PageIcon name="area" size={24} className="ae-header__logo"/>
      <h2 className="ae-header__title">Architektura projektu</h2>
    </div>
    <nav className="ae-header__crumbs" aria-label="Kde jsem">
      <span className="ae-header__step">{step}</span>
      {crumbs.map((crumb, index) => <span key={index} className="ae-header__crumb">{crumb}</span>)}
      <span className="ae-header__workspace" title={readOnly ? "Obsah stránek je zde jen pro čtení; domény a stránky jdou upravit." : undefined}>{workspace}{readOnly ? " · obsah jen pro čtení" : ""}</span>
    </nav>
    <div className="ae-header__actions">
      <button type="button" className="ae-header__id" data-testid="architecture-copy-id" title={`ID editoru: ${editorId} (kliknutím zkopírujete)`}
        aria-label="Kopírovat ID editoru" onClick={props.onCopyId}>
        <span className="ae-header__id-label">ID</span><code className="ae-header__id-value" data-testid="architecture-editor-id">{editorId}</code>
      </button>
      <button type="button" className="ae-header__button" disabled={props.exportDisabled} onClick={props.onExport}>Export JSON</button>
      <button type="button" className="ae-header__button" disabled={props.reloadDisabled} onClick={props.onReload}>Obnovit</button>
    </div>
  </header>;
}
