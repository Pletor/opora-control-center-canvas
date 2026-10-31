// „Port“: kam z karty vede vazba a co po ní dělník naposled předal. Zpráva je tvrzení autora, proto
// u ní stojí jeho značka; port bez zprávy říká jen cíl. Porty se přidávají a táhnou na kartě v plátně.
import type { PortView } from "../logic/panel-work";
import { clock, whoName } from "../logic/trail-timeline";
import SourceMark from "./SourceMark";

export default function PortSection({ ports }: { ports: PortView[] }) {
  return (
    <section className="block-panel__sec" aria-label="Port">
      <h3 className="block-panel__h">Port{ports.length > 0 && <span className="block-panel__count">{ports.length}</span>}</h3>
      {ports.length === 0 && <p className="block-panel__empty">Z karty nevede žádná vazba. Port přidáte na kartě a z jeho kuličky táhnete vazbu.</p>}
      {ports.map((port) => (
        <div key={port.key} className="block-panel__port" data-oh-edge={port.key}>
          <div className="block-panel__port-head">
            <span className="block-panel__port-label">{port.label}</span><span className="block-panel__muted" aria-hidden="true">→</span>
            <span className="block-panel__port-target">{port.target}</span>
          </div>
          {port.message.trim() && <p className="block-panel__port-msg">{port.message}</p>}
          {(port.by || port.handoff) && <div className="block-panel__port-meta">
            <SourceMark source={port.source} />
            <span>{[port.by && whoName(port.by).name, port.at && clock(port.at), port.handoff && "předáno: " + port.handoff].filter(Boolean).join(" · ")}</span>
          </div>}
        </div>
      ))}
    </section>
  );
}
