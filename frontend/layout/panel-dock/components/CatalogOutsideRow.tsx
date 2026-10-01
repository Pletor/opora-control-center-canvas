// Dílek Mimo profil: čárkovaný řádek na konci seznamu. Řekne, kolik prvků profil schoval a pro koho
// jsou („3 prvky (mikroslužby, serverless) · zobrazit“), a klikem je dočasně ukáže — nebo zase
// schová. Text i stav dostane hotové; klik hlásí `onToggle` nahoru.
export default function CatalogOutsideRow({
  summary,
  shown,
  onToggle,
}: {
  summary: string;
  shown: boolean;
  onToggle: () => void;
}) {
  return (
    <button type="button" className="catalog-scope__outside" aria-pressed={shown} data-testid="catalog-outside" onClick={onToggle}>
      Mimo profil: {summary} · <span className="catalog-scope__outside-action">{shown ? "skrýt" : "zobrazit"}</span>
    </button>
  );
}
