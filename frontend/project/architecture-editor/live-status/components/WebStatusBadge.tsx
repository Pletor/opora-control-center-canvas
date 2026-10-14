import { badgeText, badgeTitle, WEB_STATE, type WebHost } from "../logic/web-status";
import "../styles/live-status.css";

/** Žeton webu: ikona + slovo (+ latence), podrobnosti v `title`; barva jen doplňuje slovo. */
export default function WebStatusBadge({ host, stale = "" }: { host: WebHost | null; stale?: string }) {
  const meta = WEB_STATE[host?.state ?? "unchecked"];
  const title = badgeTitle(host) + (stale ? ` · ${stale}` : "");
  return <span className={`live-status__web live-status__web--${meta.tone}${stale ? " live-status__web--stale" : ""}`} title={title} data-testid={host ? "web-status-" + host.domainId : undefined}>
    <span className="live-status__icon" aria-hidden="true">{meta.icon}</span>
    <span>Web: {badgeText(host)}</span>
  </span>;
}
