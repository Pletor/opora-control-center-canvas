import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import type { CompletionEvidence } from "@/editor/canvas/node-card/components/CardEvidence";
import type { CardLease } from "@/editor/canvas/node-card/logic/use-leases";
import { leaseSeconds } from "@/editor/canvas/node-card/components/CardLease";
import { useLeaseClock } from "@/editor/card-dna/logic/lease-clock";
import { compactCheckCount } from "@/editor/card-dna/logic/compact-indicators";
import "@/editor/card-dna/styles/card-dna.css";

type Props = { pipeline?: { finished: number; total: number; failed: number }; view: CardView; evidence?: CompletionEvidence; lease?: CardLease; assignmentChanged: boolean; commit?: string; tokens?: number | null };
function CardDnaCompactLeaseIndicator({ lease }: { lease: CardLease }) {
  const seconds = leaseSeconds(lease, useLeaseClock());
  return <span title="Převzetí agentem">🤖 {lease.owner} · {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</span>;
}

/** Jedna tichá řádka orientačních signálů; velké podklady zůstávají mimo plátno. */
export default function CardDnaCompactIndicators({ pipeline, view, evidence, lease, assignmentChanged, commit, tokens }: Props) {
  const checks = compactCheckCount(view, evidence);
  return <div className="card-dna-compact__indicators" aria-label="Stav karty">
    {pipeline && <span title="Pipeline: dokončené etapy / celkem">◌ {pipeline.finished}/{pipeline.total}{pipeline.failed ? ` · ${pipeline.failed} selhání` : ""}</span>}
    {!!checks.total && <span title="Dokončené kontroly a selhání">✓ {checks.finished}/{checks.total}{checks.failed ? ` · ${checks.failed} selhání` : ""}</span>}
    {lease && <CardDnaCompactLeaseIndicator lease={lease} />}
    {assignmentChanged && <span title="Výstup vznikl pro starší zadání">↻ zadání se změnilo</span>}
    {commit && <span title="Commit realizace">⌘ {commit.slice(0, 7)}</span>}
    {tokens != null && <span title="Spotřeba tokenů">◒ {new Intl.NumberFormat("cs-CZ").format(tokens)}</span>}
  </div>;
}
