import type { Plan } from "../logic/linie-summary";
import type { WorkDetail } from "../logic/linie-work";

type Props = { plan: Plan | null; detail: WorkDetail; query: string };

const STATE: Record<string, string> = { linked: "ověřená vazba na kartu plánu", none: "bez plánu", card_missing: "karta plánu v projektu chybí", source_unavailable: "vazbu teď neověřím, karty nejdou přečíst", ambiguous: "karta má víc kandidátů směru" };
/** Odkaz na kartu plátna tak, jak ho skládá backend u detailu commitu (`screen=canvas&node=&ohCard=`). */
export const cardLink = (query: string, cardId: string) => `/?${query}&screen=canvas&node=${encodeURIComponent(cardId)}&ohCard=${encodeURIComponent(cardId)}&ohTab=steps`;

/**
 * Záložka Plán: vazba na kartu plátna 3 (a směr plátna 2) tak, jak ji backend ověřil – nic se neodvozuje z názvu.
 * Když se karta od vydání práce změnila (`diff`), stojí tu rozdíl revizí zřetelně: přijetí platí pro dvojici
 * (sha, revize zadání). Pod tím text zadání kuličky a kritéria hotovosti.
 */
export default function LinieDetailPlan({ plan, detail, query }: Props) {
  return (
    <>
      <div className="pletor-dashboard__linie-detail-card">
        <h3 className="pletor-dashboard__linie-detail-h">Plátno 2 · směr</h3>
        <p>{plan?.directionCardId ? <a href={cardLink(query, plan.directionCardId)}>karta {plan.directionCardId} ↗</a> : <span className="pletor-dashboard__note">směr neurčen (karta plánu bez záměru stránky)</span>}</p>
        <h3 className="pletor-dashboard__linie-detail-h">Plátno 3 · plán</h3>
        <p>{plan ? STATE[plan.state] ?? plan.state : "vazbu na plán board neposlal"}{plan?.text && <> · <span className="pletor-dashboard__mono">{plan.text}</span></>}</p>
        {plan?.planCardId && <p><a href={cardLink(query, plan.planCardId)}>otevřít kartu plánu ↗</a></p>}
        {plan?.issued && (
          <p className={plan.diff ? "pletor-dashboard__linie-plan-diff" : "pletor-dashboard__note"}>
            vydáno {plan.issued.at ? `${plan.issued.at.slice(0, 16).replace("T", " ")} ` : ""}pro revizi zadání R{plan.issued.cardRevision || "?"}
            {plan.diff ? `; karta je teď R${plan.cardRevision} – zadání se od vydání změnilo, přijetí platí jen pro vydanou revizi` : plan.cardRevision ? ` = aktuální R${plan.cardRevision}` : ""}
          </p>
        )}
      </div>
      <div className="pletor-dashboard__linie-detail-card">
        <h3 className="pletor-dashboard__linie-detail-h">Podstata</h3>
        <p>{detail.essence || "—"}</p>
        {detail.build && <><h3 className="pletor-dashboard__linie-detail-h">Stavba</h3><p>{detail.build}</p></>}
        <h3 className="pletor-dashboard__linie-detail-h">Kritéria hotovosti</h3>
        {detail.doneCriteria ? <ol className="pletor-dashboard__linie-criteria">{detail.doneCriteria.split("\n").filter(Boolean).map((line, i) => <li key={i}>{line}</li>)}</ol> : <p className="pletor-dashboard__note">—</p>}
      </div>
    </>
  );
}
