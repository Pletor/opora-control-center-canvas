// Jedno vlákno komunikace: kořenová zpráva a odpovědi pod ní, u každé viditelný směr, typ, stav
// převzetí a deklarovaný autor. Nic se nepotvrzuje samo; převzetí je vždy kliknutí člověka —
// a formulář toho kliknutí (`receiptForm`) skládá rodič, dílek mu jen drží místo pod tou zprávou,
// které se týká (`receiptFormFor`), aby potvrzení nikdy nestálo daleko od své zprávy.
import type { ReactNode } from "react";
import {
  MESSAGE_KIND_LABELS, RECEIPT_LABELS, directionOf, messageState, shortDigest,
  type AgentMessage, type MessageStateKey, type MessageThread, type ReceiptDisposition,
} from "@/editor/node-detail/agent-workspace/logic/agent-communication";

const stateModifier: Record<MessageStateKey, string> = {
  saved: "saved", accepted: "accepted", rejected: "rejected", needs_clarification: "needs-clarification",
};
const timestamp = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("cs-CZ");
};

type Slot = {
  /** Id zprávy, pod kterou patří otevřený formulář převzetí; jinde se nevykreslí. */
  receiptFormFor: string | null;
  receiptForm: ReactNode;
};
type CardProps = Slot & {
  message: AgentMessage; nodeId: string; superseded: boolean; orphan: boolean; reply: boolean; disabled: boolean;
  onReceipt: (message: AgentMessage, disposition: ReceiptDisposition) => void;
  onReply: (message: AgentMessage) => void;
};

function MessageCard({
  message, nodeId, superseded, orphan, reply, disabled, receiptFormFor, receiptForm, onReceipt, onReply,
}: CardProps) {
  const incoming = directionOf(message, nodeId) === "incoming";
  const state = messageState(message);
  return <article className={`agent-communication__message${reply ? " agent-communication__reply" : ""}`}>
    <div className="agent-communication__badges">
      <span className={`agent-communication__badge agent-communication__badge--${incoming ? "incoming" : "outgoing"}`}>{incoming ? "Příchozí" : "Odchozí"}</span>
      <span className="agent-communication__badge">{MESSAGE_KIND_LABELS[message.kind]}</span>
      <span className={`agent-communication__state agent-communication__state--${stateModifier[state.key]}`}>{state.label}</span>
      {superseded && <span className="agent-communication__superseded">Nahrazeno opravou</span>}
    </div>
    <div className="agent-communication__message-head">
      <span className="agent-communication__declared">Deklarovaný autor: {message.senderLabel} · identita neověřena.</span>
      <time dateTime={message.createdAt}>{timestamp(message.createdAt)}</time>
    </div>
    <p className="agent-communication__body">{message.body}</p>
    <p className="agent-communication__digest" title={message.digest}>Digest: <code>{shortDigest(message.digest)}</code></p>
    {orphan && <p className="agent-communication__orphan">Odpověď na <code>{message.replyToMessageId}</code> — původní zpráva není načtena.</p>}
    {incoming && <div className="agent-communication__receipt-actions">
      <button type="button" className="nodrag" disabled={disabled} onClick={() => onReply(message)}>Odpovědět</button>
    </div>}
    {message.receipt ? <p className="agent-communication__receipt">
      {RECEIPT_LABELS[message.receipt.disposition]} · deklarovaný příjemce: {message.receipt.recipientLabel} · identita není ověřena.
      {message.receipt.note && <> Poznámka: {message.receipt.note}</>}
    </p> : incoming && <div className="agent-communication__receipt-actions">
      <button type="button" className="nodrag" disabled={disabled} onClick={() => onReceipt(message, "accepted")}>Převzít</button>
      <button type="button" className="nodrag" disabled={disabled} onClick={() => onReceipt(message, "rejected")}>Odmítnout</button>
      <button type="button" className="nodrag" disabled={disabled} onClick={() => onReceipt(message, "needs_clarification")}>Potřebuji upřesnění</button>
    </div>}
    {receiptFormFor === message.id && receiptForm}
  </article>;
}

export default function AgentMessageThread({ thread, nodeId, disabled, receiptFormFor, receiptForm, onReceipt, onReply }: Slot & {
  thread: MessageThread; nodeId: string; disabled: boolean;
  onReceipt: (message: AgentMessage, disposition: ReceiptDisposition) => void;
  onReply: (message: AgentMessage) => void;
}) {
  const shared = { nodeId, disabled, receiptFormFor, receiptForm, onReceipt, onReply };
  return <section
    className={`agent-communication__thread${thread.pending ? " agent-communication__thread--pending" : ""}`}
    aria-label={`Vlákno: ${MESSAGE_KIND_LABELS[thread.root.kind]} · ${thread.root.senderLabel}`}
  >
    {thread.pending && <p className="agent-communication__pending">Čeká na vaše převzetí nebo odpověď.</p>}
    <MessageCard message={thread.root} superseded={thread.superseded} orphan={thread.orphan} reply={false} {...shared} />
    {thread.replies.map((message) => <MessageCard
      key={message.id} message={message} superseded={thread.supersededIds.includes(message.id)}
      orphan={false} reply {...shared}
    />)}
  </section>;
}
