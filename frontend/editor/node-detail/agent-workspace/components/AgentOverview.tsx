// Horní pás záložky Agenti: kde jsem, co čeká, co ověřit a co udělat dál — na jednu obrazovku,
// než se rozbalí jediná dlouhá sekce. Dílek nic nenačítá ani neukládá: brief i záznam prostoru
// dostává hotové od rodiče (AgentWorkspace) a jen je mapuje na text přes `overviewModel`.
// Na ploše Agenti je pás zároveň rozcestník: počty a dlaždice jsou odkazy na kotvu segmentu, kam
// se má člověk podívat. Odkazy vzniknou jen tehdy, když rodič pošle `onGoTo` — v inspektoru, kde
// žádné segmenty nestojí, zůstane pás čistým textem a nikam nemíří.
import { useMemo, type ReactNode } from "react";
import {
  READ_ONLY_TEXT,
  overviewModel,
  safetyLine,
  type OverviewModel,
} from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import type { AgentWorkspaceRecord } from "@/editor/node-detail/agent-workspace/logic/agent-workspace";
import { segmentId, type SegmentId } from "@/editor/node-detail/agent-workspace/segments/logic/agent-segments";
import type { NodeBrief } from "@/shared/desktop-state/logic/types";
import "@/editor/node-detail/agent-workspace/styles/agent-overview.css";

const WORK_LABEL: Record<OverviewModel["work"]["state"], string> = {
  empty: "Prázdná paměť", human: "Naposledy psal člověk", agent: "Naposledy psal agent",
};
const PRESENCE_LABEL = { present: "je", missing: "chybí" } as const;

/** Kam odkaz míří a co se má cestou rozbalit; `null` = plocha bez segmentů, odkaz nevzniká. */
type GoTarget = { anchor: string; go: () => void } | null;

function GoTo({ to, className, children }: { to: GoTarget; className: string; children: ReactNode }) {
  if (!to) return <span className={className}>{children}</span>;
  return <a className={`${className} agent-overview__go`} href={`#${to.anchor}`} onClick={to.go}>{children}</a>;
}

function Badge({ label, count, tone, to }: { label: string; count: number; tone: string; to: GoTarget }) {
  if (count <= 0) return null;
  return <li className={`agent-overview__badge agent-overview__badge--${tone}`}>
    <GoTo to={to} className="agent-overview__badge-text">{label} <b>{count}</b></GoTo>
  </li>;
}

function Chip({ title, value, to, children }: { title: string; value: string; to?: GoTarget; children?: ReactNode }) {
  return <article className="agent-overview__chip">
    <h4 className="agent-overview__chip-title">
      <GoTo to={to ?? null} className="agent-overview__chip-link">{title}</GoTo>
    </h4>
    <p className="agent-overview__chip-value">{value}</p>
    {children}
  </article>;
}

export default function AgentOverview({
  brief, workspaceRecord, loading, error, closed, mainReadOnly, nodeId,
  onGoTo, onExpandAll, onCollapseAll,
}: {
  brief: NodeBrief | null;
  workspaceRecord: AgentWorkspaceRecord;
  loading: boolean;
  error: string;
  /** Uzavřená karta podle briefu (`loop.done.confirmed`). */
  closed: boolean;
  /** Pohled na main bez práva zápisu (`readOnly` v briefu). */
  mainReadOnly: boolean;
  nodeId: string;
  /** Plocha se segmenty: cíl odkazu se cestou rozbalí, ať kotva nemíří do zavřeného celku. */
  onGoTo?: (id: SegmentId) => void;
  onExpandAll?: () => void;
  onCollapseAll?: () => void;
}) {
  const model = useMemo(
    () => overviewModel(brief, workspaceRecord, { closed, mainReadOnly }),
    [brief, workspaceRecord, closed, mainReadOnly],
  );
  const ready = !!brief && !loading && !error;
  // Bez briefu se nic nedomýšlí: dlaždice řeknou, proč údaj chybí, ne že je nulový.
  const pending = loading ? "Načítám…" : error ? "Brief se nenačetl" : "Bez briefu";
  const { communication: comm, verification, work } = model;
  const waiting = comm.awaitingReceipt + comm.needsClarification + comm.openQuestions;
  const savedAt = work.updatedAt ? new Date(work.updatedAt) : null;
  const saved = savedAt && !Number.isNaN(savedAt.getTime()) ? savedAt.toLocaleString("cs-CZ") : work.updatedAt;
  const to = (id: SegmentId): GoTarget =>
    onGoTo ? { anchor: segmentId(nodeId, id), go: () => onGoTo(id) } : null;
  const both = onExpandAll || onCollapseAll;

  return <section className="agent-overview" aria-label="Přehled karty pro agenta" data-testid="agent-overview">
    <div className="agent-overview__top">
      <p className="agent-overview__path">{model.path.length ? model.path.join(" / ") : nodeId}</p>
      {both && <div className="agent-overview__bulk">
        {onExpandAll && <button type="button" className="nodrag agent-overview__bulk-button" onClick={onExpandAll}>Rozbalit vše</button>}
        {onCollapseAll && <button type="button" className="nodrag agent-overview__bulk-button" onClick={onCollapseAll}>Sbalit vše</button>}
      </div>}
    </div>
    <div className="agent-overview__chips">
      <Chip title="Práce" value={WORK_LABEL[work.state]} to={to("frame")}>
        <p className="agent-overview__chip-note">
          {work.filled} z {work.total} polí · {saved || "zatím neuloženo"}
        </p>
      </Chip>
      <Chip title="Komunikace" value={!ready ? pending : !comm.available ? "Nedostupná" : waiting ? "Čeká na odpověď" : "Nic nečeká"}>
        <ul className="agent-overview__badges">
          <Badge label="Bez potvrzení" count={comm.awaitingReceipt} tone="pending" to={to("communication")} />
          <Badge label="K upřesnění" count={comm.needsClarification} tone="clarify" to={to("communication")} />
          <Badge label="Otevřené otázky" count={comm.openQuestions} tone="question" to={to("communication")} />
        </ul>
        {ready && comm.hasMore && <p className="agent-overview__chip-note">Starší zprávy zůstávají stránkované.</p>}
      </Chip>
      <Chip title="Ověření" value={!ready ? pending : `Cíl ${PRESENCE_LABEL[verification.goal]} · definice hotovo ${PRESENCE_LABEL[verification.dod]}`}>
        <ul className="agent-overview__badges">
          <Badge label="Mezery" count={verification.gaps} tone="gap" to={to("orientation")} />
        </ul>
      </Chip>
    </div>
    <p className="agent-overview__next">
      <span className="agent-overview__next-label">Další krok</span>
      {ready ? (model.nextAction.label || "Brief další krok neuvádí.") : pending}
      {ready && model.nextAction.kind && <small className="agent-overview__next-kind">{model.nextAction.kind} · doporučení, ne přijatý úkol</small>}
    </p>
    <p className="agent-overview__safety">{ready ? safetyLine(model.safety) : "Záruky se čtou z briefu karty."}</p>
    {model.readOnlyReason && <p className="agent-overview__lock">{READ_ONLY_TEXT[model.readOnlyReason]}</p>}
  </section>;
}
