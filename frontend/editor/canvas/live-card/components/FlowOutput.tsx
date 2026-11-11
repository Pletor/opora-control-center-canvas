import type { LiveFlow, LiveOutput } from "../logic/live-card-types";
import { flowColumns, sourcePath } from "../logic/live-card-view";

const W = 600, H = 170, TONES = ["vision", "mirror", "work"] as const;

/** Tok dat z plátna logiky: vstupy → kroky → výstupy jako uzly, každý sloupec propojen s dalším. */
function FlowBox({ flow }: { flow: LiveFlow }) {
  const { columns, conditions, empty } = flowColumns(flow);
  if (empty) return null;
  const nodes = columns.map((column, c) => column.map((name, r) => ({ name, x: 50 + c * (W - 100) / 2, y: (r + 1) * (H - 40) / (column.length + 1), tone: TONES[c] })));
  const links = nodes.slice(0, -1).flatMap((column, c) => column.flatMap(a => nodes[c + 1].map(b => ({ a, b }))));
  return <section className="live-card__box">
    <h3 className="live-card__h">Tok dat<small className="live-card__h-meta">{flow.name}</small></h3>
    <div className="live-card__scroll-x">
      <svg className="live-card__flow" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Tok dat ${flow.name}`}>
        {links.map(({ a, b }, i) => <path key={i} className="live-card__flow-link"
          d={`M${a.x + 17} ${a.y} C ${(a.x + b.x) / 2} ${a.y}, ${(a.x + b.x) / 2} ${b.y}, ${b.x - 17} ${b.y}`} />)}
        {nodes.flat().map((node, i) => <g key={i} className={`live-card__tone--${node.tone}`}>
          <circle className="live-card__flow-node" cx={node.x} cy={node.y} r="17" />
          <text className="live-card__flow-text" x={node.x} y={node.y + 31} textAnchor="middle">{node.name}</text>
        </g>)}
      </svg>
    </div>
    {conditions.length > 0 && <div className="live-card__chips">{conditions.map(item => <span key={item} className="live-card__chip">{item}</span>)}</div>}
    <div className="live-card__src">zdroj: <b className="live-card__src-url" title={flow.source}>{sourcePath(flow.source)}</b></div>
  </section>;
}

/** Výstup práce: snímky a náhled, na kterém se dá změna vyzkoušet. */
function OutputBox({ output }: { output: LiveOutput }) {
  if (!output.captures.length && !output.preview) return null;
  return <section className="live-card__box">
    <h3 className="live-card__h">Výstup<small className="live-card__h-meta">na čem se pracuje</small></h3>
    {output.captures.length > 0 && <div className="live-card__captures">
      {output.captures.map(item => <a key={item.url} className="live-card__capture" href={item.url} target="_blank" rel="noreferrer">
        <img className="live-card__capture-img" src={item.url} alt={item.label} loading="lazy" /><span className="live-card__capture-label">{item.label}</span>
      </a>)}
    </div>}
    {output.preview && <div className="live-card__chips"><span className="live-card__chip live-card__chip--ok">náhled {output.preview.status}</span></div>}
    <div className="live-card__src">zdroj: <b className="live-card__src-url" title={output.source}>{sourcePath(output.source)}</b></div>
  </section>;
}

export default function FlowOutput({ flow, output }: { flow: LiveFlow | null; output: LiveOutput | null }) {
  const parts = [flow && !flowColumns(flow).empty && <FlowBox key="flow" flow={flow} />,
    output && (output.captures.length > 0 || output.preview) && <OutputBox key="out" output={output} />].filter(Boolean);
  if (!parts.length) return null;
  return <div className={`live-card__row${parts.length === 1 ? " live-card__row--single" : ""}`}>{parts}</div>;
}
