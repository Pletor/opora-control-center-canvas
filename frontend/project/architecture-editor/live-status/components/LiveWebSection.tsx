import { refreshTitle } from "../logic/web-status";
import type { WebView } from "../logic/web-slots";
import { useRefreshWait } from "../logic/use-refresh-wait";
import WebStatusBadge from "./WebStatusBadge";

/**
 * Horní část živého panelu: žeton webu hostu domény a „Ověřit znovu“. Ruční ověření je zakázané
 * 30 s po poslední kontrole hostu a `title` řekne, za jak dlouho půjde („Další ověření za 18 s“).
 */
export default function LiveWebSection({ web, onRefresh }: { web: WebView; onRefresh: () => void }) {
  const wait = useRefreshWait(web.host?.checkedAt);
  return <section className="live-status__section">
    <header className="live-status__head">
      <h3 className="live-status__title">Web</h3>
      <button type="button" className="live-status__quiet" disabled={web.loading || wait > 0} onClick={onRefresh} title={refreshTitle(wait)} data-testid="live-web-refresh">
        {web.loading ? "Ověřuji…" : "Ověřit znovu"}
      </button>
    </header>
    <WebStatusBadge host={web.host} stale={web.stale}/>
    {web.host && <code className="live-status__host">{web.host.host}</code>}
    {web.stale && <small className="live-status__stale">{web.stale}</small>}
    {web.error && !web.stale && <small className="live-status__stale" role="alert">Web se nepodařilo ověřit: {web.error}</small>}
  </section>;
}
