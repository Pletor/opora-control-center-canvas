import { useEffect, useMemo, useState } from "react";
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import { buildDnaTimeline, filterDnaTimeline, type DnaTimelineGroup } from "../logic/dna-history";
import { localTimelinePage, TIMELINE_LOCAL_BATCH_SIZE } from "../logic/process-pagination";
import { useDnaHistory } from "../logic/use-dna-history";

type Props = { node: CanvasNode; data: NodeCardData; state: DesktopState; graph: Graph; project?: string; workspace?: string };
const groups: (DnaTimelineGroup | "Vše")[] = ["Vše", "Zadání", "Práce", "Ověření", "Předávky", "Kód"];
const displayTime = (at: string) => at ? new Date(at).toLocaleString() : "čas nezaznamenán";

/** Líně načtený proces nejdřív stránkuje lokální osu; teprve pak jde pro starší API stránku s before. */
export default function CardDnaProcess({ node, data, state, graph, project, workspace }: Props) {
  const [group, setGroup] = useState<DnaTimelineGroup | "Vše">("Vše");
  const [visible, setVisible] = useState(TIMELINE_LOCAL_BATCH_SIZE);
  const history = useDnaHistory(project, workspace, node.id);
  const rows = useMemo(() => filterDnaTimeline(buildDnaTimeline({ node, data, state, graph, brief: history.brief, results: history.results, messages: history.messages }), group), [data, graph, group, history.brief, history.messages, history.results, node, state]);
  const page = useMemo(() => localTimelinePage(rows, visible), [rows, visible]);
  useEffect(() => { setVisible(TIMELINE_LOCAL_BATCH_SIZE); }, [group]);
  const loadOlder = async () => {
    if (page.hasOlderLocal) { setVisible(current => current + TIMELINE_LOCAL_BATCH_SIZE); return; }
    await history.loadMore();
    setVisible(current => current + TIMELINE_LOCAL_BATCH_SIZE);
  };
  return <section className="card-dna__process">
    <header><h3>Časová osa procesu</h3><button type="button" disabled={history.loading} onClick={history.reload}>Obnovit</button></header>
    <p className="card-dna__filters">{groups.map(item => <button key={item} type="button" aria-pressed={item === group} onClick={() => setGroup(item)}>{item}</button>)}</p>
    {history.loading && <p role="status">Načítám node-brief a historii agentů…</p>}
    {history.error && <p role="alert">{history.error}</p>}
    {history.partial && <p className="card-dna__partial" role="status">Historie je částečná; starší výstupy nejsou načtené.</p>}
    {!history.loading && !history.error && <><ol className="card-dna__timeline">{page.rows.length ? page.rows.map(row => <li key={`${row.source}:${row.at}`}><time dateTime={row.at || undefined}>{displayTime(row.at)}</time> · <b>{row.group}</b> · {row.label}{row.detail ? ` — ${row.detail}` : ""}</li>) : <li>Proces zatím nemá zaznamenanou událost.</li>}</ol></>}
    {(page.hasOlderLocal || history.partial) && <button type="button" disabled={history.loadingMore} onClick={() => void loadOlder()}>{history.loadingMore ? "Načítám…" : page.hasOlderLocal ? "Zobrazit starší události" : "Načíst starší záznamy"}</button>}
  </section>;
}
