import DodBars from "@/hub/oporahub-card-drawer/components/DodBars";
import type { WorkView } from "../logic/work-view";

type Props = {
  nodeId: string;
  view: WorkView;
  /** Bez callbacku tlačítko chybí (Studio má vlastní odkaz „Otevřít v Editoru stránky“ v identitě). */
  onOpenEditor?: (id: string) => void;
};

/** Kdo kartu staví, který krok běží a kolik nálezů strážců na ní visí; bez karty v agent-state poctivě „nenapojeno“. */
function RunState({ view }: { view: WorkView }) {
  const { run, status } = view;
  return (
    <section className="element-detail__links" aria-label="Běh">
      <h4 className="element-detail__subtitle">Běh</h4>
      <p className={`element-detail__run element-detail__run--${status.health}`} data-testid="element-detail-run">
        <span aria-hidden="true">{status.glyph}</span> {status.word} · {status.stage} · {status.reason}
      </p>
      {view.connected ? (
        <dl className="element-detail__facts">
          <dt className="element-detail__fact-label">Staví</dt>
          <dd className="element-detail__fact">{run.holder ? `${run.holder}${run.expired ? " (lease vypršela)" : ""}` : "nikdo kartu nedrží"}</dd>
          <dt className="element-detail__fact-label">Běží krok</dt>
          <dd className="element-detail__fact">{run.step ? `${run.step.id}${run.step.title ? ` ${run.step.title}` : ""}` : "žádný"}</dd>
          <dt className="element-detail__fact-label">Nálezy strážců</dt>
          <dd className={`element-detail__fact${run.guards ? ` element-detail__guards element-detail__guards--${run.guards.severity}` : ""}`}>
            {run.guards ? `${run.guards.count} otevřené · nejvážnější ${run.guards.label}` : "žádný otevřený"}
          </dd>
        </dl>
      ) : null}
    </section>
  );
}

/** Záložka Práce: brány definice hotovo, kroky plánu se stavem a stav běhu; zadání a kroky se mění jen v Editoru. */
export default function WorkTab({ nodeId, view, onOpenEditor }: Props) {
  return (
    <div className="element-detail__pane">
      <DodBars dod={view.dod} tiles />
      <section className="element-detail__links" aria-label="Kroky">
        <h4 className="element-detail__subtitle">Kroky</h4>
        {view.steps?.length ? (
          <ol className="element-detail__steps">
            {view.steps.map((row) => (
              <li key={row.id} className={`element-detail__step element-detail__step--${row.status}`} data-step={row.id}
                aria-current={view.run.step?.id === row.id ? "step" : undefined}>
                <span className="element-detail__step-title">{row.title || row.id}</span>
                <span className="element-detail__step-state">{row.word}</span>
              </li>
            ))}
          </ol>
        ) : <p className="element-detail__muted">Zadání zatím nemá kroky; doplňují se v Editoru.</p>}
      </section>
      <RunState view={view} />
      {onOpenEditor ? (
        <button type="button" className="element-detail__open" onClick={() => onOpenEditor(nodeId)}>
          Otevřít v Editoru
        </button>
      ) : null}
    </div>
  );
}
