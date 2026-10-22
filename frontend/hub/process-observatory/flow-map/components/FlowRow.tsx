import { useLayoutEffect, useRef } from "react";
import type { Lane } from "../../logic/lanes";
import { PHASES, SOURCE_NAME, ago, clock, initials } from "../../logic/process-event";
import { CardHash } from "../../components/Marks";
import { markerMotion, type MarkerSeen } from "../logic/marker-motion";

type Props = { lane: Lane; selected: boolean; now: number; onSelect: (nodeId: string) => void };

const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Jedna replay třída: odebrat, vynutit reflow, přidat; po 1,5 s pryč (pulz i statický kroužek). */
function replay(element: HTMLElement, className: string) {
  element.classList.remove(className);
  void element.offsetWidth;
  element.classList.add(className);
  window.setTimeout(() => element.classList.remove(className), 1500);
}

/** Řádek karty: popisek, sedm buněk fází se stopou a značkou pracovníka a poslední událost pod nimi. */
export default function FlowRow({ lane, selected, now, onSelect }: Props) {
  const marker = useRef<HTMLSpanElement | null>(null);
  const seen = useRef<MarkerSeen | undefined>(undefined);
  const last = lane.last;
  useLayoutEffect(() => {
    const element = marker.current;
    const motion = markerMotion(seen.current, lane.phase, last && { key: last.key, kind: last.kind, state: last.state });
    seen.current = { phase: lane.phase, lastKey: last?.key ?? "" };
    if (!element || lane.stale) return;
    if (motion.shift && !reduced() && typeof element.animate === "function") {
      const cell = element.parentElement?.getBoundingClientRect().width ?? 0;
      element.animate([{ transform: `translateX(${motion.shift * cell}px)` }, { transform: "translateX(0)" }],
        { duration: 450, easing: "cubic-bezier(.2,.7,.2,1)" });
    }
    if (motion.pulse) replay(element, "flow-map__marker--pulse");
    if (motion.shake) replay(element, "flow-map__marker--shake");
  }, [lane.phase, last?.key, lane.stale]);
  const worker = lane.workerName || "bez pracovníka";
  const where = lane.source ? SOURCE_NAME[lane.source] : "bez události";
  return <div className={`flow-map__row${selected ? " flow-map__row--selected" : ""}${lane.stale ? " flow-map__row--stale" : ""}`}
    role="button" tabIndex={0} aria-pressed={selected} data-oh-card={lane.nodeId} data-oh-phase={PHASES[lane.phase][0]}
    onClick={() => onSelect(lane.nodeId)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(lane.nodeId); } }}>
    <div className="flow-map__label">
      <span className="flow-map__title" title={lane.title}>{lane.title}</span>
      <div className="flow-map__who"><CardHash id={lane.nodeId} /><span className="flow-map__worker">{worker} · {where}{lane.stale && last ? ` · naposledy ${clock(last.at)}` : ""}</span></div>
    </div>
    {PHASES.map(([id, name], index) => {
      const mark = lane.trail[index];
      const position = index < lane.phase ? "past" : index === lane.phase ? "current" : "future";
      const trail = index < lane.phase ? mark ?? "none" : index > lane.phase ? mark : null;
      const tip = index === lane.phase ? `${name} · ${last ? `${last.kind} · ${ago(last.ms, now)}` : "bez události v okně"}`
        : `${name} · ${mark ? TRAIL_WORD[mark] : "bez události"}`;
      return <div key={id} className={`flow-map__cell flow-map__cell--${position}${index === 0 ? " flow-map__cell--first" : ""}${index === PHASES.length - 1 ? " flow-map__cell--last" : ""}`} title={tip}>
        {index === lane.phase && <span ref={marker} className={`flow-map__marker flow-map__marker--${lane.marker}`} aria-label={tip}>
          {initials(lane.workerName)}{lane.marker === "blocked" && <span className="flow-map__bang" aria-hidden="true">!</span>}
        </span>}
        {trail && <span className={`flow-map__trail flow-map__trail--${trail}${index > lane.phase ? " flow-map__trail--ahead" : ""}`} />}
      </div>;
    })}
    <div className={`flow-map__last flow-map__last--${last?.state ?? "none"}`}>
      {last ? <><span className="flow-map__time">{clock(last.at)}</span><span className="flow-map__kind">{last.kind}</span>
        <span className="flow-map__text">{last.title}</span></>
        : <span className="flow-map__text">Bez události v okně · etapa {lane.card?.stage ?? "—"}{lane.card?.reason ? ` · ${lane.card.reason}` : ""}</span>}
    </div>
  </div>;
}

export const TRAIL_WORD = { ok: "potvrzeno", fail: "selhalo", wait: "čeká", seen: "proběhlo bez potvrzení", none: "bez události" } as const;
