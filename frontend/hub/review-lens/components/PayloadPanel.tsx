import type { GraphDoc } from "@coldtea/pr-lens-schema";
import { payloadDiff } from "../logic/payload-diff";
import { DELTA_WORD } from "./CardPanel";

type Side = NonNullable<NonNullable<GraphDoc["flows"][number]["messages"][number]["payload"]>["request"]>;
const SIGN = { added: "+", removed: "−", changed: "~", same: " " } as const;

function PayloadSide({ name, side }: { name: string; side: Side }) {
  const rows = side.sample === undefined ? [] : payloadDiff(side.sample, side.before);
  return <div className="review-lens__payload" data-oh-lens-payload={name}>
    <h4 className="review-lens__panel-label">{name} <code>{side.type}</code></h4>
    {side.shape && <pre className="review-lens__code">{side.shape}</pre>}
    {rows.length > 0 && <table className="review-lens__diff">
      <thead><tr><th>cesta</th><th>před</th><th>po</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.path} className={`review-lens__diff-row review-lens__diff-row--${row.status}`} data-oh-diff={row.status}>
        <td><span aria-hidden="true">{SIGN[row.status]} </span><code>{row.path}</code></td>
        <td><code>{row.before ?? ""}</code></td><td><code>{row.after ?? ""}</code></td></tr>)}</tbody>
    </table>}
    {side.before === undefined && side.sample !== undefined && <p className="review-lens__muted">Spec neuvádí ukázku před změnou.</p>}
  </div>;
}

/** Panel kroku toku: kdo komu co posílá, jak se to změnilo a tvar a ukázka payloadu (před/po barevně). */
export default function PayloadPanel({ doc, flowId, messageId, onClose }: { doc: GraphDoc; flowId: string; messageId: string; onClose: () => void }) {
  const flow = doc.flows.find(item => item.id === flowId);
  const message = flow?.messages.find(item => item.id === messageId);
  if (!flow || !message) return null;
  const label = (id: string) => doc.nodes.find(item => item.id === id)?.label ?? id;
  return <section className="review-lens__panel" data-oh-lens-step={messageId} data-oh-lens-flow={flowId}>
    <div className="review-lens__panel-head">
      <span className={`review-lens__chip review-lens__chip--${message.delta}`}>{DELTA_WORD[message.delta] ?? message.delta}</span>
      <code className="review-lens__muted">{message.kind} · {flow.title}</code>
      <span className="review-lens__grow" />
      <button type="button" className="review-lens__close" aria-label="Zavřít payload" onClick={onClose}>✕</button>
    </div>
    <h3 className="review-lens__panel-title">{message.label}</h3>
    <p className="review-lens__panel-text">{label(message.from)} → {label(message.to)}</p>
    {message.payload?.request && <PayloadSide name="request" side={message.payload.request} />}
    {message.payload?.response && <PayloadSide name="response" side={message.payload.response} />}
    {!message.payload && <p className="review-lens__muted">Krok nenese payload.</p>}
  </section>;
}
