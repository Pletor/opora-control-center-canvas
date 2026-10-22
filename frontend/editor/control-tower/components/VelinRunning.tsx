// „Teď běží“: karty s živým pronájmem — agent, krok, postup a odpočet. Prošlý pronájem je červený s ✕,
// aby šel poznat i bez barvy. Odpočet tiká jednou za sekundu jen tady, ne na celé stránce.
import type { CSSProperties } from "react";
import { countdown } from "@/editor/canvas/card-face/logic/face-labels";
import { useNow } from "@/editor/canvas/card-face/logic/use-now";
import type { VelinPill } from "../logic/velin-model";

export default function VelinRunning({ running, onOpen }: { running: VelinPill[]; onOpen: (nodeId: string) => void }) {
  const now = useNow(1000, running.length > 0);
  return (
    <section className="velin__running" aria-label="Teď běží">
      <header className="velin__panel-head"><b>Teď běží</b><span className="velin__grow" /><small className="velin__muted">agent · krok · postup · lease</small></header>
      {!running.length && <p className="velin__muted velin__panel-row">Žádný agent teď nedrží kartu.</p>}
      {running.map(pill => {
        const lease = pill.face.lease;
        const left = lease ? countdown(lease.expiresAt, now) : "vypršel";
        const late = left === "vypršel";
        const steps = pill.face.steps;
        return (
          <button key={pill.nodeId} type="button" className={"velin__run" + (late ? " velin__run--late" : "")} onClick={() => onOpen(pill.nodeId)}
            data-oh-node-id={pill.nodeId} data-oh-lease-holder={lease?.holder ?? ""} data-oh-lease-expires={lease?.expiresAt ?? ""}>
            <span className="velin__avatar">A</span>
            <b className="velin__run-name">{pill.name}</b>
            <code className="velin__run-who">{late && !lease ? "— lease vypršela" : `${(lease?.holder ?? "agent").replace(/^agent:/, "")} · ${steps.label} (${steps.count})`}</code>
            <span className="velin__run-bar"><i style={{ "--share": `${steps.total ? Math.round(100 * steps.done / steps.total) : 0}%` } as CSSProperties} /></span>
            <span className="velin__run-left">{late ? "✕ 00:00" : left}</span>
          </button>
        );
      })}
    </section>
  );
}
