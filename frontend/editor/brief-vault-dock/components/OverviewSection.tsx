// Přehled plánu: jedna věta stavu, pruh pokrytí, dlaždice Výzkum · K upřesnění · Změněno po vložení
// a seznam „Čeká na tebe“. Klik vede do příslušné sekce (onSection). Jen zobrazení.
import { countChangedMvp, coverageOf, type Feedback, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import CoverageBar, { chaptersLabel } from "@/editor/node-detail/brief-vault/components/CoverageBar";
import { VERDICTS, questionItems, verdictCounts, waitingOnHuman, type SectionId } from "../logic/vault-dock-model";

export default function OverviewSection({ roots, feedback, onSection }: {
  roots: VaultNode[];
  feedback: Feedback[];
  onSection: (id: SectionId) => void;
}) {
  const coverage = coverageOf(roots);
  const verdicts = verdictCounts(roots);
  const research = Object.values(verdicts).reduce((sum, value) => sum + value, 0);
  const open = questionItems(roots).filter((item) => !item.node.question?.answered);
  const waiting = waitingOnHuman(roots, feedback);
  const asCards = coverage.inserted + coverage.mvpInserted + coverage.changed;
  const verdictHint = (Object.keys(VERDICTS) as (keyof typeof VERDICTS)[]).filter((key) => verdicts[key])
    .map((key) => `${verdicts[key]} ${VERDICTS[key].label}`).join(" · ");
  return (
    <div className="vault-stack" data-testid="vault-overview">
      <p className="vault-overview__headline">
        {coverage.leaves} {chaptersLabel(coverage.leaves)} zadání · {asCards} už {asCards === 1 ? "pracuje" : "pracují"} jako karty
      </p>
      <CoverageBar coverage={coverage} large changedMvp={countChangedMvp(roots)} />
      <div className="vault-grid">
        <button type="button" className="vault-tile" onClick={() => onSection("research")}>
          <span className="vault-tile__label">Výzkum</span>
          <span className="vault-tile__value">{research}</span>
          <span className="vault-tile__hint">{verdictHint || "Zatím žádný výzkum proveditelnosti."}</span>
        </button>
        <button type="button" className="vault-tile" onClick={() => onSection("questions")}>
          <span className="vault-tile__label">K upřesnění</span>
          <span className="vault-tile__value">{open.length}</span>
          <span className="vault-tile__hint">{open.slice(0, 2).map((item) => item.node.title).join(" · ") || "Žádná otevřená otázka."}</span>
        </button>
        <button type="button" className="vault-tile" onClick={() => onSection("tree")}>
          <span className="vault-tile__label">Změněno po vložení</span>
          <span className="vault-tile__value">{coverage.changed}</span>
          <span className="vault-tile__hint">{coverage.changed ? "Karty vznikly ze starší revize textu." : "Karty mají aktuální zadání."}</span>
        </button>
      </div>
      <section className="vault-panel" aria-label="Čeká na tebe">
        <h3 className="vault-panel__title">Čeká na tebe</h3>
        {waiting.length ? waiting.map((item) => (
          <div key={item.id} className="vault-waiting">
            <span className={"brief-vault__dot brief-vault__dot--" + item.tone} aria-hidden="true" />
            <span className="vault-waiting__text">{item.text}</span>
            <button type="button" className="vault-button" onClick={() => onSection(item.section)}>{item.action}</button>
          </div>
        )) : <p className="vault-panel__text">Nic nečeká: výzkum má zpětnou vazbu, otázky odpovědi a karty aktuální zadání.</p>}
      </section>
    </div>
  );
}
