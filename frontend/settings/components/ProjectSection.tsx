/** Projekt: operace nad aktuálním projektem, dříve v menu horní lišty. Každé tlačítko má skutečný handler. */
export type ProjectActions = {
  name: string;
  localProject: boolean;
  busy: boolean;
  onProjectSettings: () => void;
  onRefresh: () => void;
  onSync: () => void;
  onRemoveProject: () => void;
};

export default function ProjectSection({ actions, onClose }: { actions: ProjectActions; onClose: () => void }) {
  const run = (action: () => void) => () => {
    onClose();
    action();
  };
  return (
    <section className="settings-section" aria-labelledby="project-title">
      <h3 id="project-title">Projekt · {actions.name}</h3>
      <p className="muted">Operace nad aktuálním projektem. Git operace se lokálnímu návrhu nenabízejí.</p>
      <div className="settings-row">
        <span>Zadání a nastavení projektu v přehledu projektu.</span>
        <button type="button" onClick={run(actions.onProjectSettings)}>Nastavení projektu</button>
      </div>
      <div className="settings-row">
        <span>Znovu načíst plátno a stav z disku.</span>
        <button type="button" disabled={actions.busy} onClick={run(actions.onRefresh)}>Obnovit pohled</button>
      </div>
      {!actions.localProject && (
        <>
          <div className="settings-row">
            <span>Aktualizuje jen čistou spravovanou kopii. Žádný push.</span>
            <button type="button" disabled={actions.busy} onClick={run(actions.onSync)}>Synchronizovat main</button>
          </div>
          <div className="settings-row">
            <span>Odebere ze seznamu; GitHub ani soubory se nemažou.</span>
            <button type="button" className="danger" disabled={actions.busy} onClick={run(actions.onRemoveProject)}>Odebrat repozitář</button>
          </div>
        </>
      )}
    </section>
  );
}
