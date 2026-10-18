// Stavová věta karty: jedna věta pod procesem (docs/proces-karty.md §3) a u návrhu uzavření tlačítko Potvrdit.
// Dobu práce počítá dílek z `since` při vykreslení, aby data karty nenesla běžící čas.
import { useEffect, useState } from "react";
import ConfirmProposal from "./ConfirmProposal";
import { sinceLabel, type CardStateLine } from "../logic/card-state";
import type { EvidenceReadiness } from "../logic/evidence-readiness";

const MARK: Record<CardStateLine["tone"], string> = { ok: "✓", warn: "◷", fail: "🔒", run: "●", idle: "◉" };

export default function CardState({ line, completion, confirm, disabled }: {
  line: CardStateLine;
  completion?: { note?: string; readiness?: EvidenceReadiness; error?: string };
  confirm?: () => Promise<boolean>;
  disabled: boolean;
}) {
  // Doba práce běží v dílku po minutách; data karty zůstávají stabilní pro hluboké porovnání.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!line.since) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(timer);
  }, [line.since]);
  const since = line.since ? sinceLabel(line.since, now) : "";
  const detail = [line.detail, since].filter(Boolean).join(" · ");
  return (
    <div className={"node-card__state node-card__state--" + line.tone} role="status">
      <span className="node-card__state-mark" aria-hidden="true">{MARK[line.tone]}</span>
      <span className="node-card__state-text">{line.text}</span>
      {detail && <span className="node-card__state-detail" title={detail}>{detail}</span>}
      {line.confirm && confirm && completion && (
        <ConfirmProposal confirm={confirm} note={completion.note} readiness={completion.readiness} serverError={completion.error} disabled={disabled} />
      )}
    </div>
  );
}
