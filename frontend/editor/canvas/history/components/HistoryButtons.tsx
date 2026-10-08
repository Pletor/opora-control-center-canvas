// Tlačítka Zpět / Vpřed v liště Editoru ve skupině Pohled. Dílek nic neví o historii: dostane, jestli je kam
// krokovat, a klik hlásí nahoru. Krok sám (uložení snímku nebo obnova smazaného) dělá App stejnou
// cestou jako Ctrl+Z / Ctrl+Shift+Z, takže tlačítko a klávesa nikdy nedělají každé něco jiného.
import "@/editor/canvas/history/styles/history.css";

export default function HistoryButtons({ canUndo, canRedo, onUndo, onRedo }: {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
}) {
  return (
    <div className="history-buttons" role="group" aria-label="Historie plátna" data-testid="history-buttons">
      <button type="button" className="history-buttons__step" title="Zpět (Ctrl+Z)" aria-label="Zpět"
        disabled={!canUndo} onClick={onUndo} data-testid="history-undo">
        <span className="history-buttons__glyph" aria-hidden="true">↶</span>
        <span className="history-buttons__label">Zpět</span>
      </button>
      <button type="button" className="history-buttons__step" title="Vpřed (Ctrl+Shift+Z)" aria-label="Vpřed"
        disabled={!canRedo} onClick={onRedo} data-testid="history-redo">
        <span className="history-buttons__glyph" aria-hidden="true">↷</span>
        <span className="history-buttons__label">Vpřed</span>
      </button>
    </div>
  );
}
