// Ikonka Historie uložení vedle ULOŽIT: otevírá a zavírá panel verzí. Otevřenost drží rodič.
export default function SaveHistoryButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button type="button" className="save-versions__history" title="Historie uložení" aria-label="Historie uložení"
      aria-pressed={open} aria-haspopup="dialog" aria-expanded={open} onClick={onToggle} data-testid="save-history">
      <span className="save-versions__glyph" aria-hidden="true">↺</span>
    </button>
  );
}
