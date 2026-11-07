import { shortSha, type LinieGraphView } from "../logic/linie-view";

/** Stav main v jedné řádce pod lištou: lokál a origin, server, nasazení, ochrana a zápis nasazení = HEAD serveru. */
export default function LinieStatus({ view, onDeployed }: { view: LinieGraphView; onDeployed: (sha: string) => void }) {
  const main = view.lanes.find((item) => item.role === "main");
  return (
    <p className="pletor-dashboard__linie-status">
      <span className="pletor-dashboard__mono">main {shortSha(main?.sha ?? "") || "—"} lokál / {shortSha(main?.remote ?? "") || "—"} origin</span>
      <span className="pletor-dashboard__mono">server: {view.server.branch || "—"} @ {shortSha(view.server.sha) || "—"}{view.server.dirty ? " (necommitnuté změny)" : ""}</span>
      <span className="pletor-dashboard__mono">nasazeno: {view.deployed ? `${shortSha(view.deployed.sha)} ${view.deployed.at}` : "neevidováno"}</span>
      <span className="pletor-dashboard__tag pletor-dashboard__tag--warn">ochrana: {view.enforcement}</span>
      <button type="button" className="pletor-dashboard__button" disabled={!view.server.sha} onClick={() => onDeployed(view.server.sha)}>Zapsat nasazené = HEAD serveru</button>
    </p>
  );
}
