// „Stopa práce“: jedna osa, kde leží relace dělníků i změny karty za sebou (nic dvakrát), rozdělená po dnech.
// Rozbalená je jen nejnovější relace; ostatní se rozbalí klikem. Celou historii má detail karty.
import { useState } from "react";
import type { TimelineGroup, TimelineItem } from "../logic/trail-timeline";
import { clock, runState, whoName } from "../logic/trail-timeline";
import SourceMark from "./SourceMark";
import TrailRunBody from "./TrailRunBody";

function RunItem({ item, filesKnown }: { item: Extract<TimelineItem, { kind: "run" }>; filesKnown: boolean }) {
  const [open, setOpen] = useState(item.expanded);
  const state = runState(item.run.state);
  const who = whoName(item.run.owner);
  const steps = item.run.steps.length;
  return (
    <li className="block-panel__tl-item" data-oh-run={item.run.executionId ?? item.run.taskId ?? ""}>
      <span className={"block-panel__tl-dot block-panel__tl-dot--" + state.tone} aria-hidden="true" />
      <button type="button" className="block-panel__tl-row block-panel__tl-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <b className={"block-panel__name block-panel__name--" + who.kind}>{who.name}</b>
        <span>{item.run.taskId ? "úkol brány" : "relace"} · {state.word}{steps ? ` · ${steps} ${steps === 1 ? "krok" : steps < 5 ? "kroky" : "kroků"}` : ""}</span>
        <span className="block-panel__tl-time">{clock(item.at)}</span>
        <span className="block-panel__chev" aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open && <TrailRunBody run={item.run} filesKnown={filesKnown} />}
    </li>
  );
}

function EventItem({ item }: { item: Extract<TimelineItem, { kind: "event" }> }) {
  const who = whoName(item.event.who);
  return (
    <li className="block-panel__tl-item" data-oh-event={item.event.kind}>
      <span className={"block-panel__tl-dot block-panel__tl-dot--" + (who.kind === "heart" ? "gold" : "idle")} aria-hidden="true" />
      <div className="block-panel__tl-row">
        <SourceMark source={item.event.source} />
        <span className="block-panel__tl-text"><b className={"block-panel__name block-panel__name--" + who.kind}>{who.name}</b> · {item.event.label || item.event.kind}</span>
        <span className="block-panel__tl-time">{clock(item.at)}</span>
      </div>
    </li>
  );
}

export default function TrailSection({ groups, filesKnown, onHistory }: { groups: TimelineGroup[]; filesKnown: boolean; onHistory: () => void }) {
  const count = groups.reduce((sum, group) => sum + group.items.length, 0);
  return (
    <section className="block-panel__sec" aria-label="Stopa práce">
      <h3 className="block-panel__h">Stopa práce<span className="block-panel__h-meta">{count ? `posledních ${count}` : ""}</span></h3>
      {count === 0 ? <p className="block-panel__empty">Na kartě zatím nikdo nepracoval. Až ji dělník převezme branou, objeví se tu kdo, do kdy a co udělal.</p>
        : <ul className="block-panel__tl">
          {groups.map((group) => [
            <li key={"day:" + group.day} className="block-panel__tl-day">{group.label}</li>,
            ...group.items.map((item) => item.kind === "run"
              ? <RunItem key={item.key} item={item} filesKnown={filesKnown} />
              : <EventItem key={item.key} item={item} />),
          ])}
        </ul>}
      <button type="button" className="block-panel__link" onClick={onHistory}>Celá historie →</button>
    </section>
  );
}
