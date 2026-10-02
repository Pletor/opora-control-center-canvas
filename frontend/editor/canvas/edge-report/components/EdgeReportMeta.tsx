// Hlavička předání nad textovými poli zprávy (docs/kontext-karet-a-index.md §4): From a To s názvem
// a čitelnou adresou karty, Sent (kdy se naposledy změnilo předání) — vše jen ke čtení — a Date, termín
// převzetí, který člověk smí nastavit. Dílek nic neukládá: změnu termínu ohlásí přes onDue.
import { formatSent, type EdgeRoute } from "@/editor/canvas/edge-report/logic/edge-report-model";

export default function EdgeReportMeta({
  route,
  sentAt,
  due,
  readOnly,
  busy,
  onDue,
}: {
  route: EdgeRoute;
  sentAt: string | undefined;
  due: string | undefined;
  readOnly: boolean;
  busy: boolean;
  onDue: (due: string) => void;
}) {
  const end = (label: string, testId: string, value: EdgeRoute["from"]) => (
    <div className="edge-report__meta-row" data-testid={testId}>
      <span className="edge-report__meta-label">{label}</span>
      <span className="edge-report__meta-value">
        {value.name}
        {value.address && <code className="edge-report__meta-address">{value.address}</code>}
      </span>
    </div>
  );
  return (
    <div className="edge-report__meta" aria-label="Předání na vazbě">
      {end("From", "edge-report-from", route.from)}
      {end("To", "edge-report-to", route.to)}
      <div className="edge-report__meta-row" data-testid="edge-report-sent">
        <span className="edge-report__meta-label">Sent</span>
        <span className={"edge-report__meta-value" + (sentAt ? "" : " edge-report__meta-value--empty")} title={sentAt || undefined}>
          {formatSent(sentAt)}
        </span>
      </div>
      <label className="edge-report__meta-row">
        <span className="edge-report__meta-label">Date</span>
        <input
          type="date"
          className="edge-report__meta-date"
          aria-label="Termín převzetí"
          data-testid="edge-report-due"
          value={due ?? ""}
          readOnly={readOnly}
          disabled={busy || readOnly}
          onChange={(e) => onDue(e.target.value)}
        />
      </label>
    </div>
  );
}
