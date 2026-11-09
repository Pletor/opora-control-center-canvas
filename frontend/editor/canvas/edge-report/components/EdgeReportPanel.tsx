// Panel vybrané vazby: odkud kam vede, z jakého portu (u vazby z bloku i z kterého tlačítka) a pět
// pojmenovaných polí zprávy, kterou tam agent nebo člověk nechává pro dalšího v řadě. Dílek nic neukládá:
// rozepsaný text drží u sebe a po opuštění pole ho ohlásí nahoru přes onChange; ukládá rodič (App).
import EdgeRelationEditor from "@/editor/canvas/edge-report/components/EdgeRelationEditor";
import type { GraphEdge } from "@/shared/types/logic/types";
import { useState } from "react";
import type { EdgeReport, EdgeReportField } from "@/shared/desktop-state/logic/types";
import { EDGE_REPORT_FIELDS, MAX_REPORT_FIELD } from "@/shared/desktop-state/logic/types";
import { filledFields, reportSignature, type EdgeReportView, type EdgeRoute } from "@/editor/canvas/edge-report/logic/edge-report-model";
import EdgeReportMeta from "@/editor/canvas/edge-report/components/EdgeReportMeta";
import "@/editor/canvas/edge-report/styles/edge-report.css";

export default function EdgeReportPanel({
  view,
  route,
  report,
  readOnly,
  busy,
  onChange,
  onDue,
  onDelete,
  edge,
  onEdgeChange,
}: {
  edge?: GraphEdge;
  onEdgeChange?: (edge: GraphEdge) => void;
  view: EdgeReportView;
  /** From / To: název a adresa obou karet z `edgeRoute`. */
  route: EdgeRoute;
  report: EdgeReport;
  readOnly: boolean;
  busy: boolean;
  /** Opuštění pole ohlásí hotovou hodnotu; rodič ji uloží přes desktop.mutate(setEdgeReport(...)). */
  onChange: (field: EdgeReportField, value: string) => void;
  /** Nový termín převzetí (`YYYY-MM-DD` nebo `""`); rodič ho uloží přes setEdgeReport(..., { due }). */
  onDue: (due: string) => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState<Partial<Record<EdgeReportField, string>>>({});
  const value = (field: EdgeReportField) => draft[field] ?? report[field];
  const commit = (field: EdgeReportField) => {
    const next = draft[field];
    setDraft((current) => ({ ...current, [field]: undefined }));
    if (next !== undefined && next !== report[field]) onChange(field, next);
  };
  const signature = reportSignature(report);
  return (
    <div className="edge-report" data-testid="edge-report-panel">
      <div className="edge-report__eyebrow">VAZBA · {view.portLabel}</div>
      <h2 className="edge-report__route">
        {view.sourceName} <span className="edge-report__arrow" aria-hidden="true">→</span> {view.targetName}
      </h2>
      {view.blockNumber && (
        <p className="edge-report__origin">
          Z bloku <b>{view.blockNumber}</b> {view.blockTitle}
          {view.portName && <> · port <b>{view.portName}</b></>}
        </p>
      )}
      <p className="edge-report__note">
        Zpráva na vazbě je paměť mezi kartami: co se udělalo, co z toho platí a na co si má dát pozor další agent.
        Vyplněno <b>{filledFields(report)} / {EDGE_REPORT_FIELDS.length}</b>. Identifikátor vazby: <code>{view.edgeId}</code>
      </p>
      {edge && onEdgeChange && <EdgeRelationEditor key={edge.id} edge={edge} readOnly={readOnly} busy={busy} onSave={onEdgeChange} />}
      <EdgeReportMeta route={route} sentAt={report.sentAt} due={report.due} readOnly={readOnly} busy={busy} onDue={onDue} />
      <div className="edge-report__fields">
        {EDGE_REPORT_FIELDS.map((field) => (
          <label key={field.id} className="edge-report__field">
            <span className="edge-report__label">{field.label}</span>
            <textarea
              className="edge-report__input"
              aria-label={field.label}
              data-testid={"edge-report-" + field.id}
              title={field.hint}
              rows={3}
              maxLength={MAX_REPORT_FIELD}
              readOnly={readOnly}
              disabled={busy}
              value={value(field.id)}
              onChange={(e) => setDraft((current) => ({ ...current, [field.id]: e.target.value }))}
              onBlur={() => commit(field.id)}
            />
            <small className="edge-report__hint">{field.hint}</small>
          </label>
        ))}
      </div>
      <p className="edge-report__signature">
        {signature ? <>Naposledy zapsal {signature}</> : "Na této vazbě zatím nikdo nic nevysvětlil."}
      </p>
      <button
        type="button"
        className="edge-report__delete danger"
        disabled={readOnly || busy}
        title={readOnly ? "Main je pouze pro čtení." : "Zobrazit dopad před smazáním"}
        onClick={onDelete}
      >
        Smazat vazbu
      </button>
    </div>
  );
}
