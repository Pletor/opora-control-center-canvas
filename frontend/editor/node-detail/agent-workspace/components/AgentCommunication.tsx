// Rozbalitelný výpis zpráv kolem jedné karty. Otevření jako jediný okamžik spouští čtení; akce
// převzetí jsou vždy vědomé a deklarovaná jména se nikdy nevydávají za ověřenou identitu.
// Formulář převzetí patří ke své zprávě: stojí přímo pod ní ve vlákně a v hlavičce se hlásí,
// kterou zprávu a jakou akci potvrzuje. Otevřený je vždy nejvýš jeden. Po úspěšném převzetí nebo
// odeslání se ohlásí rodiči (`onChanged`), aby přehled nad panelem nezůstal na starých počtech;
// dokud nejsou zprávy načtené, mluví zavřená hlavička počtem z briefu (`pendingHint`).
import { useMemo, useState } from "react";
import {
  MESSAGE_KINDS, MESSAGE_KIND_LABELS, buildThreads, canCreateReceipt, canSendMessage,
  emptyMessageDraft, pendingCount, pendingSummary, receiptHeadline, replyDraft,
  type AgentMessage, type MessageDraft, type ReceiptDisposition,
} from "@/editor/node-detail/agent-workspace/logic/agent-communication";
import { useAgentCommunication } from "@/editor/node-detail/agent-workspace/logic/use-agent-communication";
import AgentMessageThread from "@/editor/node-detail/agent-workspace/components/AgentMessageThread";
import "@/editor/node-detail/agent-workspace/styles/agent-communication.css";

export default function AgentCommunication({ project, workspace, nodeId, readOnly, pendingHint, onChanged }: {
  project: string; workspace: string; nodeId: string; readOnly: boolean;
  /** Počet nevyřízených z briefu; platí jen do chvíle, než panel načte vlastní zprávy. */
  pendingHint?: number;
  /** Potvrzené převzetí nebo odeslaná zpráva; rodič si podle toho obnoví přehled karty. */
  onChanged?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<MessageDraft>(emptyMessageDraft);
  const [receipt, setReceipt] = useState<{ message: AgentMessage; disposition: ReceiptDisposition } | null>(null);
  const [recipientLabel, setRecipientLabel] = useState("");
  const [receiptNote, setReceiptNote] = useState("");
  const model = useAgentCommunication({ project, workspace, nodeId }, open);
  const blocked = readOnly || model.readOnly;
  const id = `agent-communication-${nodeId}`;
  const update = <K extends keyof MessageDraft>(key: K, value: MessageDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const threads = useMemo(
    () => buildThreads(model.incoming.messages, model.outgoing.messages),
    [model.incoming.messages, model.outgoing.messages],
  );
  // Dokud panel nemá vlastní zprávy, je jediným pravdivým počtem ten z briefu; pak mluví načtená data.
  const pending = pendingSummary(model.loaded ? pendingCount(threads) : Math.max(0, Math.trunc(pendingHint ?? 0)));
  const receiptDraft = { disposition: receipt?.disposition ?? "accepted", note: receiptNote, recipientLabel };

  async function send() {
    if (!await model.send(draft, readOnly)) return;
    setDraft(emptyMessageDraft());
    onChanged?.();
  }
  async function saveReceipt() {
    if (!receipt) return;
    if (!await model.receipt(receipt.message, { ...receiptDraft, disposition: receipt.disposition }, readOnly)) return;
    // Formulář se zavírá až po potvrzeném zápisu; při chybě zůstane u své zprávy i s rozepsanou poznámkou.
    setReceipt(null);
    setReceiptNote("");
    onChanged?.();
  }

  const receiptForm = receipt && !blocked
    ? <section className="agent-communication__receipt-form" aria-label="Potvrzení převzetí">
      <h4 className="agent-communication__receipt-headline" title={receipt.message.digest}>
        {receiptHeadline(receipt.message, receipt.disposition)}
      </h4>
      <p>Potvrzení je záznam deklarovaného příjemce, nikoli ověřené oprávnění.</p>
      <label htmlFor={`${id}-recipient`}>Jméno / role příjemce (deklarováno)<input id={`${id}-recipient`} maxLength={120} value={recipientLabel} onChange={(e) => setRecipientLabel(e.target.value)} /></label>
      <label htmlFor={`${id}-note`}>Poznámka{receipt.disposition !== "accepted" ? " (povinná)" : " (volitelná)"}<textarea id={`${id}-note`} rows={3} maxLength={12000} value={receiptNote} onChange={(e) => setReceiptNote(e.target.value)} /></label>
      <div className="agent-communication__receipt-form-actions">
        <button type="button" className="nodrag" disabled={model.writing || !canCreateReceipt(receiptDraft, blocked)} onClick={() => void saveReceipt()}>Potvrdit akci</button>
        <button type="button" className="nodrag" disabled={model.writing} onClick={() => { setReceipt(null); setReceiptNote(""); }}>Zrušit</button>
      </div>
    </section>
    : null;

  return <details className="agent-communication" open={open} onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}>
    <summary className="agent-communication__summary">{pending ? `Komunikace mezi agenty · ${pending}` : "Komunikace mezi agenty"}</summary>
    <div className="agent-communication__content">
      <p className="agent-communication__notice">Identita není ověřena; potvrzení nepřevádí oprávnění.</p>
      {blocked && <p className="agent-communication__readonly">Karta je uzavřená nebo main je jen ke čtení; zápis není dostupný.</p>}
      {model.error && <p className="agent-communication__error" role="alert">{model.error}</p>}
      <div className="agent-communication__toolbar"><span>{model.loading ? "Načítám zprávy…" : "Nejnovější vlákno nahoře"}</span><button type="button" className="nodrag" onClick={() => void model.reload()} disabled={model.loading}>Zpět na nejnovější</button></div>
      <section className="agent-communication__threads" aria-label="Vlákna zpráv">
        {!threads.length && !model.loading && <p className="muted">Zatím žádné zprávy.</p>}
        {threads.map((thread) => <AgentMessageThread
          key={thread.root.id} thread={thread} nodeId={nodeId} disabled={blocked || model.writing}
          receiptFormFor={receipt?.message.id ?? null} receiptForm={receiptForm}
          onReceipt={(message, disposition) => { setReceipt({ message, disposition }); setReceiptNote(""); }}
          onReply={(message) => setDraft((current) => replyDraft(current, message))}
        />)}
      </section>
      {(model.incoming.hasMore || model.outgoing.hasMore) && <footer className="agent-communication__footer">
        {model.incoming.hasMore && <button type="button" className="nodrag" disabled={model.loading} onClick={() => void model.loadOlder("incoming")}>Starší zprávy · příchozí</button>}
        {model.outgoing.hasMore && <button type="button" className="nodrag" disabled={model.loading} onClick={() => void model.loadOlder("outgoing")}>Starší zprávy · odchozí</button>}
      </footer>}
      {!blocked && <section className="agent-communication__form" aria-label="Nová zpráva">
        <h4>Nová zpráva</h4>
        {draft.replyToMessageId && <p className="agent-communication__reply-target">Odpovídáte na <code>{draft.replyToMessageId}</code><button type="button" className="nodrag" onClick={() => update("replyToMessageId", null)}>Zrušit odpověď</button></p>}
        <label htmlFor={`${id}-target`}>Příjemce<select id={`${id}-target`} value={draft.targetNodeId} onChange={(e) => update("targetNodeId", e.target.value)}><option value="">Vyberte kartu</option>{model.targets.map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}</select></label>
        <label htmlFor={`${id}-kind`}>Typ<select id={`${id}-kind`} value={draft.kind} onChange={(e) => update("kind", e.target.value as MessageDraft["kind"])}>{MESSAGE_KINDS.map((kind) => <option key={kind} value={kind}>{MESSAGE_KIND_LABELS[kind]}</option>)}</select></label>
        <label htmlFor={`${id}-body`}>Zpráva<textarea id={`${id}-body`} rows={4} maxLength={12000} value={draft.body} onChange={(e) => update("body", e.target.value)} /></label>
        <label htmlFor={`${id}-sender`}>Jméno / role (deklarováno)<input id={`${id}-sender`} maxLength={120} value={draft.senderLabel} onChange={(e) => update("senderLabel", e.target.value)} /></label>
        <button type="button" className="nodrag" disabled={model.writing || !canSendMessage({ project, workspace, nodeId }, draft, blocked)} onClick={() => void send()}>Odeslat zprávu</button>
      </section>}
    </div>
  </details>;
}
