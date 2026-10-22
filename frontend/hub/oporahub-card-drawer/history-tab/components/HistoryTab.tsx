import { useState } from "react";
import CardHistory from "@/hub/oporahub-card-history/components/CardHistory";
import type { CardEvents } from "../../logic/use-card-events";
import { EVENT_FILTERS, FILTER_LABEL, eventTime, eventTitle, eventTone, matchesFilter, type EventFilter } from "../logic/card-events";
import "../styles/history-tab.css";

function exportEvents(nodeId: string, events: CardEvents["events"]) {
  const url = URL.createObjectURL(new Blob([JSON.stringify({ nodeId, events }, null, 2)], { type: "application/json" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: `udalosti-${nodeId}.json` });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Záložka Historie: časová osa událostí karty (filtr Vše/Zadání/Běh/Review/Lidé) a historie + blame zadání. */
export default function HistoryTab({ project, workspace, nodeId, events }: { project: string; workspace: string; nodeId: string; events: CardEvents }) {
  const [filter, setFilter] = useState<EventFilter>("all");
  const shown = events.events.filter(item => matchesFilter(item, filter));
  const first = events.events.at(-1);
  return <div className="history-tab" data-oh-view="card-events" data-oh-node-id={nodeId} data-oh-events-head={events.head}
    data-oh-events-count={events.events.length} data-oh-events-truncated={String(events.truncated)} data-oh-events-filter="client">
    <div className="history-tab__bar">
      <div className="history-tab__filters" role="group" aria-label="Filtr událostí">
        {EVENT_FILTERS.map(item => <button key={item} type="button" className="history-tab__filter" aria-pressed={filter === item}
          onClick={() => setFilter(item)}>{FILTER_LABEL[item]}</button>)}
      </div>
      <code className="history-tab__muted">události · kurzor #{events.head}</code>
    </div>
    {events.error && <p className="history-tab__muted" role="alert">{events.error}</p>}
    {events.busy && !events.events.length && <p className="history-tab__muted" role="status">Načítám události…</p>}
    {events.truncated && <p className="history-tab__muted">Zobrazeny události z prvních stránek toku; starší část zkrácena.</p>}
    {events.gap && <p className="history-tab__muted">◌ Retence smazala část starších událostí.</p>}
    <ol className="history-tab__list" aria-label="Události karty">
      {shown.map(item => <li key={item.id} className="history-tab__event" data-oh-event={item.id} data-oh-event-kind={item.kind}
        data-oh-step={item.stepId ?? undefined} data-oh-execution={item.executionId ?? undefined}>
        <time className="history-tab__time" dateTime={item.at}>{eventTime(item.at)}</time>
        <span className={`history-tab__dot history-tab__dot--${eventTone(item)}`} aria-hidden="true" />
        <span className="history-tab__text"><b>{eventTitle(item)}</b>
          <code className="history-tab__muted"> · {item.kind} · {item.actor.name}</code></span>
      </li>)}
      {!events.busy && !shown.length && <li className="history-tab__muted">◌ Pro kartu zatím žádná událost{filter !== "all" ? " v tomto filtru" : ""}.</li>}
    </ol>
    <CardHistory project={project} workspace={workspace} nodeId={nodeId} />
    <div className="history-tab__foot">
      <span><b>{events.events.length} událostí</b>{first && <span className="history-tab__muted"> · od {new Date(first.at).toLocaleDateString("cs-CZ")}</span>}</span>
      <button type="button" className="history-tab__button" disabled={!events.events.length} onClick={() => exportEvents(nodeId, events.events)}>Export</button>
    </div>
  </div>;
}
