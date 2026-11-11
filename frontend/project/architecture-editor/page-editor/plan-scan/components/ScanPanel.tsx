import type { ComponentProps } from "react";
import type { PageScan } from "../logic/use-page-scan";
import { ADOPT_LABELS, type AdoptResult } from "../logic/adopt-scan";
import ScanParts from "./ScanParts";
import "../styles/plan-scan.css";

type Props = Omit<ComponentProps<typeof ScanParts>, "proposal"> & {
  scan: PageScan;
  /** Výsledek posledního převzetí po částech; `null` = ještě nepřevzato. */
  report: AdoptResult[] | null;
  /** Zrušit čekání na běžící sken nebo zavřít chybu či výsledek (jen lokálně). */
  onCancel: () => void;
};

/** Panel skenu vedle plátna: průběh (Zrušit), chyba, návrh po částech (`ScanParts`: Převzít / Zahodit), nebo po převzetí
 * výsledek každé části (co se převzalo a co ne a proč). Dílek nic neukládá; převzetí a Zahodit hlásí rodiči. */
export default function ScanPanel({ scan, report, onCancel, ...parts }: Props) {
  if (scan.phase === "idle") return null;
  return <aside className="plan-scan" aria-label="Sken webu" data-testid="architecture-scan-panel">
    <header className="plan-scan__head">
      <strong className="plan-scan__head-title">Návrh ze skenu webu</strong>
      {scan.phase === "done" && scan.cost !== null && <small className="plan-scan__cost">{scan.cost.toFixed(2)} USD</small>}
    </header>
    {(scan.phase === "starting" || scan.phase === "running") && <div className="plan-scan__progress" role="status">
      <span className="plan-scan__spinner" aria-hidden="true"/>
      <span>{scan.phase === "starting" ? "Spouštím sken…" : `Výzkumník prochází web… ${Math.round(scan.elapsed / 1000)} s`}</span>
      <button type="button" onClick={onCancel}>Zrušit</button>
    </div>}
    {scan.phase === "failed" && <div className="plan-scan__failed">
      <p className="plan-scan__error" role="alert">{scan.error}</p>
      <button type="button" onClick={onCancel}>Zavřít</button>
    </div>}
    {scan.phase === "done" && (report ? <div className="plan-scan__report" data-testid="architecture-scan-report">
      <ul className="plan-scan__results">
        {report.map((result, index) => <li key={index} className={"plan-scan__result plan-scan__result--" + (result.ok ? "ok" : "failed")}>
          <span aria-hidden="true">{result.ok ? "✓" : "✕"}</span> <strong>{ADOPT_LABELS[result.part]}</strong> {result.text}</li>)}
      </ul>
      <div className="plan-scan__actions">
        <button type="button" onClick={onCancel}>Zavřít</button>
        {!report.some((result) => result.part === "layout" && result.ok) && <button type="button" onClick={parts.onDiscard}>Zahodit návrh</button>}
      </div>
      {parts.discardError && <p className="plan-scan__error" role="alert">{parts.discardError}</p>}
    </div> : <ScanParts proposal={scan.proposal} {...parts}/>)}
  </aside>;
}
