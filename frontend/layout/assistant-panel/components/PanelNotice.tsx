/**
 * Oznámení místo kanálu, když není s kým mluvit: chybí projekt. Řekne, co se stalo a co má uživatel udělat.
 */
export default function PanelNotice() {
  return (
    <div className="assistant-panel__notice">
      <p className="assistant-panel__notice-title">Vyberte projekt</p>
      <p className="assistant-panel__notice-text">Srdce pracuje nad jedním projektem. Zvolte ho v horní liště a kanál se objeví tady.</p>
    </div>
  );
}
