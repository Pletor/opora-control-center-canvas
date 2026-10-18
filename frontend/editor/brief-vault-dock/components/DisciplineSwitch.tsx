// Přepínač disciplín nahoře ve Schránce (docs/schranka-neurony.md §6): tři skupiny Kreslení · Logika · Provoz,
// v nich jen zapnuté neurony (disciplína s živým fragmentem) s počtem fragmentů v rozsahu, vpravo „Nezařazené“.
// Jen zobrazení; vybranou disciplínu drží rodič (BriefVaultDock) a volbu hlásí callbackem.
import { GROUPS, UNASSIGNED, type Discipline, type DisciplineView } from "../logic/disciplines";

export default function DisciplineSwitch({ view, live, counts, onView }: {
  view: DisciplineView;
  /** Zapnuté neurony v pořadí tabulky §2. */
  live: Discipline[];
  counts: Record<DisciplineView, number>;
  onView: (view: DisciplineView) => void;
}) {
  const chip = (id: DisciplineView, label: string, title: string) => (
    <button key={id} type="button" className="vault-dock__discipline" aria-pressed={view === id} title={title}
      data-testid={"vault-discipline-" + id} onClick={() => onView(id)}>
      {label}
      <span className="vault-dock__discipline-count">{counts[id] ?? 0}</span>
    </button>
  );
  return (
    <div className="vault-dock__disciplines" role="group" aria-label="Disciplína schránky">
      {GROUPS.map((group) => {
        const items = live.filter((item) => item.group === group.id);
        return (
          <div key={group.id} className="vault-dock__discipline-group" role="group" aria-label={group.label}>
            <span className="vault-dock__discipline-label">{group.label}</span>
            {items.length ? items.map((item) => chip(item.id, item.label, `${group.label} · ${item.label}`))
              : <span className="vault-dock__discipline-sleep" title="Žádná disciplína skupiny zatím nemá živý fragment.">spí</span>}
          </div>
        );
      })}
      <div className="vault-dock__discipline-group vault-dock__discipline-group--end">
        {chip(UNASSIGNED, "Nezařazené", "Fragmenty bez disciplíny na celé cestě ke kořeni (z doby před disciplínami). Strukturu z nich server nesloží.")}
      </div>
    </div>
  );
}
