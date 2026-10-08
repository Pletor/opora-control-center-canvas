import type { ScenarioHistory } from "../logic/use-scenario-history";
import { safeDesignUrl } from "./CardDesign";

export default function CardScenario({ command, history, error }: { command: string; history?: ScenarioHistory; error?: string }) {
  const run = history?.latest;
  const current = !!history?.current && run?.command === command;
  const trend = history?.comparable ? (history.deltaFailed! < 0 ? "↗" : history.deltaFailed! > 0 ? "↘" : "→") : "";
  return <details className="nodrag nopan" style={{ padding: "6px 12px" }}>
    <summary style={{ color: current ? run!.failed ? "#ef4444" : "#22c55e" : "inherit" }}>
      E2E {run ? `${run.passed}/${run.passed + run.failed} ${current ? run.failed ? "✗" : "✓" : "· starý příkaz"} · ${new Date(run.at).toLocaleTimeString()} ${trend}` : error ? "nedostupné" : "zatím bez běhu"}
    </summary>
    <code>{command}</code>
    {error && <p role="alert">{error}</p>}
    {run && <><p>OK {run.passed} · FAIL {run.failed}</p>{!!run.failed && <p style={{ color: "#ef4444" }}>První nesplněný krok: {run.firstFailure}</p>}
      {safeDesignUrl(run.logUrl) && <a href={run.logUrl} target="_blank" rel="noopener noreferrer">Log posledního běhu</a>}</>}
    {history?.previous && <p>Předchozí: {history.previous.passed} OK / {history.previous.failed} FAIL · {history.previous.at}</p>}
    {history?.comparable ? <p>Změna: OK {history.deltaPassed! >= 0 ? "+" : ""}{history.deltaPassed}, FAIL {history.deltaFailed! >= 0 ? "+" : ""}{history.deltaFailed}</p> : run && <p>Pro tento příkaz zatím nejsou dva porovnatelné běhy.</p>}
  </details>;
}
