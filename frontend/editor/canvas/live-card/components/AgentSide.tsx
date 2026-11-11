import type { OporaEvent } from "@/editor/live-strip/logic/events-client";
import type { LiveAgent } from "../logic/live-card-types";
import { clock, sourceShape } from "../logic/live-card-view";
import JsonBlock from "./JsonBlock";

type Props = {
  nodeId: string; mark: string | null; agent: LiveAgent | null; souhrn: unknown; tvar: unknown; briefError: string; raw: OporaEvent[];
  onPanel: () => void; onCopy: (text: string) => void;
};
const methodTone = (method: string) => method.toUpperCase() === "GET" ? "get" : method.toUpperCase() === "SSE" ? "sse" : "post";

/** Rub pro agenty: adresa, vrstvy node-brief jako JSON, čtení a zápis s metodou a rolí, spouštěče, syrový proud. */
export default function AgentSide({ nodeId, mark, agent, souhrn, tvar, briefError, raw, onPanel, onCopy }: Props) {
  return <>
    <div className="live-card__addr">
      <span className="live-card__muted">adresa</span>
      <code className="live-card__addr-code">{agent?.address ?? `opora://card/${nodeId}`}</code>
      <button type="button" className="live-card__button" onClick={() => onCopy(agent?.address ?? `opora://card/${nodeId}`)}>Kopírovat</button>
      <span className="live-card__addr-meta">lease: {agent?.lease ? `${agent.lease.holder} do ${clock(agent.lease.until)}` : "volná"}{agent?.revision != null ? ` · rev ${agent.revision}` : ""}</span>
      <button type="button" className="live-card__button live-card__button--go" onClick={onPanel}>Pracovní panel</button>
    </div>
    {briefError && <p className="live-card__alert" role="alert">{briefError}</p>}
    <div className="live-card__row">
      <section className="live-card__box"><h3 className="live-card__h">#souhrn</h3>{souhrn != null ? <JsonBlock value={souhrn} /> : <p className="live-card__muted">Načítám…</p>}</section>
      <section className="live-card__box"><h3 className="live-card__h">#tvar</h3>{tvar != null ? <JsonBlock value={tvar} tall /> : <p className="live-card__muted">Načítám…</p>}</section>
    </div>
    {agent && agent.reads.length > 0 && <section className="live-card__box"><h3 className="live-card__h">Čtení po vrstvách</h3>
      <div className="live-card__scroll-x"><table className="live-card__table"><tbody>
        {agent.reads.map(read => <tr key={read.layer + read.url}>
          <td className="live-card__cell-key">{read.layer}</td><td className={`live-card__method live-card__method--${methodTone(read.method)}`}>{read.method}</td>
          <td className="live-card__cell" title={read.url}>{sourceShape(read.url)}</td><td className="live-card__cell live-card__muted">{read.size ?? ""}</td>
          <td className="live-card__cell"><span className={`live-card__tag${read.exists ? " live-card__tag--live" : " live-card__tag--new"}`}>{read.exists ? "existuje" : "staví se"}</span></td>
        </tr>)}
      </tbody></table></div></section>}
    {agent && (agent.writes.length > 0 || agent.triggers.length > 0) && <div className="live-card__row">
      {agent.writes.length > 0 && <section className="live-card__box"><h3 className="live-card__h">Zápis (jen nástroji, s rolí)</h3>
        <div className="live-card__scroll-x"><table className="live-card__table"><tbody>
          {agent.writes.map((write, index) => <tr key={index}>
            <td className="live-card__cell-key">{write.role}</td><td className={`live-card__method live-card__method--${methodTone(write.method)}`}>{write.method}</td>
            <td className="live-card__cell">{write.url}</td><td className="live-card__cell live-card__muted">{write.what}</td>
          </tr>)}
        </tbody></table></div></section>}
      {agent.triggers.length > 0 && <section className="live-card__box"><h3 className="live-card__h">Spouštěče karty</h3>
        <table className="live-card__table"><tbody>
          {agent.triggers.map((trigger, index) => <tr key={index}><td className="live-card__cell-key">{trigger.when}</td><td className="live-card__cell live-card__muted">→ {trigger.then}</td></tr>)}
        </tbody></table></section>}
    </div>}
    <div className="live-card__row">
      <section className="live-card__box"><h3 className="live-card__h">#deník · syrový proud</h3>
        {raw.length ? <pre className="live-card__pre live-card__pre--tall">{raw.map(event => JSON.stringify(event)).join("\n")}</pre>
          : <p className="live-card__muted">Od otevření karty nepřišla žádná událost.</p>}</section>
      <section className="live-card__box"><h3 className="live-card__h">Nástroje</h3>
        <pre className="live-card__pre">{`uv run python tools/linie.py task
uv run python tools/linie.py report \\
  --check "npm test=green" --try "ohCard=${nodeId}" --step "…"${mark ? `
uv run python tools/linie.py trace --mark ${mark}` : ""}`}</pre></section>
    </div>
  </>;
}
