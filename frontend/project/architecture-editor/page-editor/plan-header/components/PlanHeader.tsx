import { useState, type ReactNode } from "react";
import MapCheckPanel from "../../../domain-site/map-check/components/MapCheckPanel";
import type { MapCheckGroup, MapCheckTarget } from "../../../domain-site/map-check/logic/map-check";
import PageIcon from "../../components/PageIcon";
import "../styles/plan-header.css";

type Props = {
  title: string; complete: boolean; tools?: ReactNode;
  /** Díry kontroly mapy této stránky; null = kontrola není načtená (tlačítko je vypnuté). */
  check: MapCheckGroup[] | null; onOpenFinding: (target: MapCheckTarget) => void;
  /** Kompletní stránka zavřená pro úpravy: věta a „Otevřít k úpravám“ (uvolní zámek pro toto sezení u rodiče). */
  sealed: boolean; onReopen: () => void;
  /** Skenovat web (okno skládá rodič); `scanBusy` = sken už běží nebo čeká na rozhodnutí. */
  onScan?: () => void; scanBusy?: boolean;
};

/** Hlavička plátna 2: název stránky, Skenovat web, Zkontrolovat plán (díry této stránky pod hlavičkou), stav stránky. */
export default function PlanHeader({ title, complete, tools, check, onOpenFinding, sealed, onReopen, onScan, scanBusy }: Props) {
  const [checking, setChecking] = useState(false);
  return <>
    <header className="plan-header">
      <PageIcon name="page" size={22} className="plan-header__icon"/>
      <div className="plan-header__text">
        <h2 className="plan-header__title">{title}</h2>
        <p className="plan-header__lead">Co stránka umí, jak funguje a co je potřeba vytvořit</p>
      </div>
      {tools}
      {onScan && <button type="button" className="plan-header__scan" disabled={scanBusy} data-testid="architecture-scan-web" onClick={onScan}>⌕ Skenovat web</button>}
      <button type="button" className="plan-header__check" aria-expanded={checking} disabled={!check} data-testid="architecture-check-plan"
        onClick={() => setChecking(!checking)}>✓ Zkontrolovat plán</button>
      <span className={"plan-header__status" + (complete ? " plan-header__status--complete" : "")} data-testid="architecture-page-status">{complete ? "Kompletní" : "Rozpracováno"}</span>
    </header>
    {checking && check && <div className="plan-header__findings"><MapCheckPanel groups={check} onSelect={onOpenFinding}/></div>}
    {sealed && <div className="plan-header__sealed" role="status">
      <span>Stránka je kompletní. Plátno je jen pro čtení.</span>
      <button type="button" data-testid="architecture-reopen-page" onClick={onReopen}>Otevřít k úpravám</button>
    </div>}
  </>;
}
