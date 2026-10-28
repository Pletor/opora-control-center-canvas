// Strážci ve Velínu: jeden tichý řádek „Strážci ✓“ nebo „Strážci ⚠ N“ s časem posledního běhu a chybou strážce,
// pod ním otevřené nálezy (block první). Klik na nález s kartou otevře její detail stejně jako ostatní položky Velínu.
import { SEVERITY_GLYPH, SEVERITY_LABEL, type GuardLine, type VelinGuardItem } from "../logic/velin-guards";

const time = (value: string | null) => value ? new Date(value).toLocaleTimeString("cs-CZ") : "—";

export default function VelinGuards({ line, findings, onOpen }: {
  line: GuardLine | null; findings: VelinGuardItem[] | null; onOpen: (nodeId: string) => void;
}) {
  if (!line && !findings) return null;
  return (
    <section className="velin__guards" aria-label="Strážci" data-oh-guards={line ? (line.ok ? "ok" : line.count) : ""}>
      {line && <p className={"velin__guard-line" + (line.ok ? "" : " velin__guard-line--alert")}>
        <b>Strážci {line.ok ? "✓" : `⚠ ${line.count}`}</b>
        <span className="velin__guard-meta">poslední běh {time(line.lastRunAt)}</span>
        {line.errors.map(item => <span key={item.id} className="velin__guard-error" title={item.error}>chyba strážce: {item.label}</span>)}
      </p>}
      {findings && findings.length > 0 && <ul className="velin__guard-list">
        {findings.map(item => (
          <li key={item.key}>
            <button type="button" className={"velin__guard velin__guard--" + item.severity} disabled={!item.nodeId}
              onClick={() => item.nodeId && onOpen(item.nodeId)} title={`${SEVERITY_LABEL[item.severity]} · ${item.rule}`}
              data-oh-guard-key={item.key} data-oh-node-id={item.nodeId ?? ""} data-oh-severity={item.severity}>
              <span className="velin__guard-glyph" aria-hidden="true">{SEVERITY_GLYPH[item.severity]}</span>
              <span className="velin__guard-text">{item.message}</span>
              <small className="velin__guard-card">{item.cardName || item.guard}</small>
            </button>
          </li>
        ))}
      </ul>}
    </section>
  );
}
