import { useCallback, useMemo, useState } from "react";
import "../styles/heart-channel.css";
import { useHeartChannel } from "../logic/use-heart-channel";
import { useBatchSteps } from "../logic/use-batch-steps";
import { stepRows } from "../logic/heart-live";
import Escalations from "./Escalations";
import GateOff from "./GateOff";
import HeartComposer from "./HeartComposer";
import HeartLive from "./HeartLive";
import HeartState from "./HeartState";
import Queue from "./Queue";

const NO_NODES: { id: string; name: string }[] = [];

/**
 * Kanál člověka do srdce (docs/brain-heart-channel.md §1): jeden sloupec shora otázky srdce, fronta
 * úkolů, stav srdce a pole pro zprávu. Rodič kanálu: drží načtená data (`useHeartChannel`) a koncept
 * zprávy, dílky dostávají hotová data a hlásí volby nahoru. Stav brány dodá panel asistenta
 * (`gateOn`, `null` = ještě se zjišťuje, `gateFailure`) a zapnutí brány hlásí nahoru `onEnableGate`.
 * Karty plátna (`nodes`) dávají krokům srdce jména; karta mimo graf zůstane svým ID.
 */
export default function HeartChannel({
  active,
  projectId,
  workspace,
  gateOn,
  gateFailure,
  onEnableGate,
  nodes = NO_NODES,
}: {
  active: boolean;
  projectId: string;
  workspace: string;
  gateOn: boolean | null;
  gateFailure: string;
  onEnableGate: () => void;
  nodes?: { id: string; name: string }[];
}) {
  const data = useHeartChannel(active && gateOn === true, projectId, workspace);
  const batches = useBatchSteps(projectId);
  const liveSteps = useMemo(() => stepRows(data.liveSteps, nodes), [data.liveSteps, nodes]);
  const batchSteps = useCallback((key: string) => {
    const found = batches.byBatch[key];
    return found ? { loading: found.loading, error: found.error, steps: stepRows(found.entries, nodes) } : null;
  }, [batches.byBatch, nodes]);
  const current = data.status?.running ? data.status.current : null;
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    if (await data.send(text)) setDraft("");
    setSending(false);
  }, [draft, sending, data.send]);

  if (gateOn === null) return <p className="heart-channel__note">Zjišťuji stav brány projektu…</p>;
  if (!gateOn) return <GateOff failure={gateFailure} onEnable={onEnableGate} />;

  return (
    <section className="heart-channel" aria-label="Srdce">
      <div className="heart-channel__scroll">
        {data.failure && (
          <p role="alert" className="heart-channel__error">
            <span className="heart-channel__error-text">{data.failure}</span>
            <button type="button" className="heart-channel__error-dismiss" aria-label="Skrýt chybu" onClick={() => data.setFailure("")}>×</button>
          </p>
        )}
        <Escalations escalations={data.escalations} onAnswer={data.answer} />
        <Queue tasks={data.tasks} loaded={data.loaded} />
        <HeartState status={data.status} live={current ? <HeartLive current={current} steps={liveSteps} /> : null}
          batchSteps={batchSteps} onOpenBatch={batches.load} />
      </div>
      <HeartComposer value={draft} sending={sending} onChange={setDraft} onSend={() => void send()} />
    </section>
  );
}
