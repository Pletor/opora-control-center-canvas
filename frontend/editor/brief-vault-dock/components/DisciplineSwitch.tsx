// Přepínač disciplín nahoře ve Schránce (docs/schranka-neurony.md §6): hlavičky Kreslení · Logika · Provoz jsou záložky.
// Rozbalená je jen skupina vybrané disciplíny a v ní zapnuté neurony s počtem fragmentů v rozsahu; ostatní hlavičky
// nesou počet zapnutých neuronů (spící „spí“) a kolik věcí v nich čeká na člověka. „Čeká na tebe“ proklikává disciplíny,
// kde na člověka něco čeká; vpravo „Nezařazené“. Jen zobrazení; vybranou disciplínu drží rodič a volbu hlásí callbackem.
import { GROUPS, UNASSIGNED, type Discipline, type DisciplineView } from "../logic/disciplines";
import { activeGroup, groupTarget, groupWaiting, nextWaiting, totalWaiting, type WaitingCounts } from "../logic/discipline-groups";

export default function DisciplineSwitch({ view, live, counts, waiting = {}, onView, onWaiting }: {
  view: DisciplineView;
  /** Zapnuté neurony v pořadí tabulky §2. */
  live: Discipline[];
  counts: Record<DisciplineView, number>;
  /** Kolik věcí čeká na člověka v každé disciplíně (`waitingByDiscipline`). */
  waiting?: WaitingCounts;
  onView: (view: DisciplineView) => void;
  /** Proklik „Čeká na tebe“: rodič přepne disciplínu a ukáže seznam v Přehledu. */
  onWaiting?: (view: DisciplineView) => void;
}) {
  const open = activeGroup(view, live);
  const badge = (n: number) => (n > 0
    ? <span className="vault-dock__waiting-badge" title={`${n} čeká na tebe`} aria-label={`${n} čeká na tebe`}>{n}</span>
    : null);
  const chip = (id: DisciplineView, label: string, title: string) => (
    <button key={id} type="button" className="vault-dock__discipline" aria-pressed={view === id} title={title}
      data-testid={"vault-discipline-" + id} onClick={() => onView(id)}>
      {label}
      <span className="vault-dock__discipline-count">{counts[id] ?? 0}</span>
      {badge(waiting[id] ?? 0)}
    </button>
  );
  const next = nextWaiting(view, live, waiting);
  return (
    <div className="vault-dock__disciplines" role="group" aria-label="Disciplína schránky">
      {GROUPS.map((group) => {
        const items = live.filter((item) => item.group === group.id);
        const target = groupTarget(group.id, live, counts, waiting);
        const isOpen = open === group.id;
        return (
          <div key={group.id} className={"vault-dock__discipline-group" + (isOpen ? " vault-dock__discipline-group--open" : "")}
            role="group" aria-label={group.label}>
            <button type="button" className="vault-dock__discipline-head" aria-expanded={isOpen} disabled={!target}
              data-testid={"vault-group-" + group.id}
              title={target ? `Ukázat disciplíny skupiny ${group.label}` : "Žádná disciplína skupiny zatím nemá živý fragment."}
              onClick={() => { if (target) onView(isOpen ? view : target); }}>
              {group.label}
              <span className="vault-dock__discipline-count">{items.length ? items.length : "spí"}</span>
              {badge(groupWaiting(group.id, live, waiting))}
            </button>
            {isOpen && items.map((item) => chip(item.id, item.label, `${group.label} · ${item.label}`))}
          </div>
        );
      })}
      <div className="vault-dock__discipline-group vault-dock__discipline-group--end">
        {next && (
          <button type="button" className="vault-dock__discipline vault-dock__discipline--waiting" data-testid="vault-waiting-next"
            title="Přejít na další disciplínu, kde něco čeká na tebe" onClick={() => (onWaiting ?? onView)(next)}>
            Čeká na tebe
            <span className="vault-dock__discipline-count">{totalWaiting(waiting)}</span>
          </button>
        )}
        {chip(UNASSIGNED, "Nezařazené", "Fragmenty bez disciplíny na celé cestě ke kořeni (z doby před disciplínami). Strukturu z nich server nesloží.")}
      </div>
    </div>
  );
}
