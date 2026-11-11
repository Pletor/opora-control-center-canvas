// Data živé karty: jedno čtení `GET /api/oporahub/live-card`, živý deník ze sdíleného toku událostí
// (filtr karty na klientovi, jen události novější než první snímek) a na rubu node-brief po vrstvách.
// Sdílený klient (`eventsClient`) místo vlastního SSE: neotevírá další spojení (strop 8 streamů na server)
// a už umí mezeru, znovupřipojení i polling.
import { useEffect, useMemo, useRef, useState } from "react";
import { useUiSession } from "@/hub/oporahub-card-drawer/logic/use-card-data";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { scopeQuery } from "@/hub/oporahub-mirror/logic/hub-read";
import { eventsClient, type OporaEvent } from "@/editor/live-strip/logic/events-client";
import { parseBrief, parseLiveCard, type RecentItem } from "./live-card-types";
import { eventToRecent, mergeRecent, prependRecent } from "./live-card-view";

const RAW_MAX = 20;

export function useLiveCard(project: string, workspace: string, nodeId: string, withBrief: boolean) {
  const session = useUiSession();
  const scoped = !!project && !!workspace && !!nodeId && session;
  const query = scopeQuery({ project, workspace, nodeId });
  const card = useHubRead(scoped ? `/api/oporahub/live-card?${query}` : null, parseLiveCard);
  const souhrn = useHubRead(scoped && withBrief ? `/api/desktop-v3/node-brief?${query}&layer=souhrn` : null, parseBrief);
  const tvar = useHubRead(scoped && withBrief ? `/api/desktop-v3/node-brief?${query}&layer=tvar` : null, parseBrief);

  const [live, setLive] = useState<{ recent: RecentItem[]; raw: OporaEvent[] }>({ recent: [], raw: [] });
  const seen = useRef<number | null>(null);
  useEffect(() => {
    if (!project || !workspace || !nodeId) return;
    seen.current = null;
    setLive({ recent: [], raw: [] });
    return eventsClient.subscribe(project, workspace, snapshot => {
      if (snapshot.transport === "connecting") return;
      const top = snapshot.events.at(-1)?.id ?? snapshot.cursor;
      // První snímek je historie, tu nese `recent` z API; deník bere jen to, co přijde potom.
      if (seen.current === null) { seen.current = top; return; }
      const fresh = snapshot.events.filter(event => event.id > (seen.current ?? 0) && event.nodeId === nodeId).reverse();
      seen.current = Math.max(seen.current, top);
      if (fresh.length) setLive(current => ({ recent: prependRecent(current.recent, fresh.map(eventToRecent)), raw: [...fresh, ...current.raw].slice(0, RAW_MAX) }));
    });
  }, [project, workspace, nodeId]);

  const recent = useMemo(() => mergeRecent(card.data?.recent ?? [], live.recent), [card.data, live.recent]);
  const reload = () => { card.reload(); souhrn.reload(); tvar.reload(); };
  return { card: card.data, busy: card.busy || !session, error: card.error, recent, raw: live.raw,
    souhrn: souhrn.data, tvar: tvar.data, briefError: souhrn.error || tvar.error, reload };
}
export type LiveCardData = ReturnType<typeof useLiveCard>;
