import type { PletorAction } from "../logic/linie-actions";
import type { Judgement } from "../logic/linie-summary";
import type { WorkDetail } from "../logic/linie-work";
import LinieTrial from "./LinieTrial";

type Props = {
  judgement: Judgement | null; detail: WorkDetail; cluster: { ticketId: string; title: string }[]; onPick: (ticketId: string) => void;
  actions: PletorAction[]; onAct: (id: string) => void;
};

const short = (sha: string) => sha.slice(0, 7);
const AXIS_LABEL: Record<string, Record<string, string>> = {
  work: { not_started: "nezačato", in_progress: "probíhá", submitted: "odevzdáno" },
  checks: { missing: "chybí", running: "běží", passed: "prošly", failed: "selhaly" },
  acceptance: { pending: "čeká", accepted: "přijato", stale: "zastaralo", stale_plan: "zastaralo (zadání)" },
  integration: { none: "nezačleněno", merged: "začleněno" },
};

/**
 * Záložka Souhrn: pět os, každá s hodnotou, revizí a zdrojem; pravidlo souhrnu strojově (monospace) a další krok
 * týmž textem jako v panelu Pletora. Chybějící osa je „nevím“, nikdy „není“. Pak náhled se zkouškou a novinkami od ní,
 * pod tím výčet shluku „+N“.
 */
export default function LinieDetailSummary({ judgement, detail, cluster, onPick, actions, onAct }: Props) {
  const a = judgement?.axes;
  const word = (axis: string, state: string) => (state ? AXIS_LABEL[axis]?.[state] ?? state : "nevím");
  const envs = a ? Object.entries(a.deploy.envs) : [];
  const rows: [string, string, string, string][] = a ? [
    ["práce", word("work", a.work.state), "", a.work.src],
    ["kontroly", word("checks", a.checks.state), short(a.checks.sha), a.checks.src],
    ["přijetí", word("acceptance", a.acceptance.state), short(a.acceptance.sha), a.acceptance.src],
    ["začlenění", `${word("integration", a.integration.state)}${a.integration.target ? ` do ${a.integration.target}` : ""}${a.integration.mode ? ` · ${a.integration.mode}` : ""}`, short(a.integration.sha), a.integration.src],
    ["nasazení", envs.length ? envs.map(([env, sha]) => `${env}@${short(sha)}`).join(", ") : "nepotvrzeno", "", a.deploy.src],
  ] : [];
  const next = judgement?.summary.next || detail.next;
  return (
    <>
      <div className="pletor-dashboard__linie-detail-card">
        <h3 className="pletor-dashboard__linie-detail-h">Pět os · každá s důkazem a zdrojem</h3>
        {a ? rows.map(([k, value, sha, src]) => (
          <div key={k} className="pletor-dashboard__linie-axis-row">
            <span className="pletor-dashboard__linie-k">{k}</span><strong>{value}</strong>
            <span className="pletor-dashboard__mono">{sha}</span><span className="pletor-dashboard__note">{src || "zdroj neuveden"}</span>
          </div>
        )) : <p className="pletor-dashboard__note">Osy s důkazy backend neposlal; stav: {judgement?.summary.text || detail.stateLabel || "nevím"}.</p>}
        {judgement && judgement.incomplete.length > 0 && <p className="pletor-dashboard__note">neúplné zdroje: {judgement.incomplete.join(", ")} (chybějící data = „nevím“, ne „není“)</p>}
        <h3 className="pletor-dashboard__linie-detail-h">Pravidlo souhrnu</h3>
        <p className="pletor-dashboard__mono">{judgement?.summary.reason || "—"}</p>
        <h3 className="pletor-dashboard__linie-detail-h">Další krok (ze stejného pravidla)</h3>
        <p>{next || "—"}</p>
      </div>
      <LinieTrial trial={detail.trial} actions={actions} onAct={onAct} news />
      {cluster.length > 0 && (
        <div className="pletor-dashboard__linie-detail-card">
          <h3 className="pletor-dashboard__linie-detail-h">Ve shluku · {cluster.length}</h3>
          {cluster.map((item) => <button key={item.ticketId} type="button" className="pletor-dashboard__linie-crumb-back" onClick={() => onPick(item.ticketId)}>{item.title}</button>)}
        </div>
      )}
    </>
  );
}
