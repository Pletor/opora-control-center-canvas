// Podrobnosti vybrané karty v jednom foldu (docs/proces-karty.md §1): doklady s odkazy a běhy kontrol, kdo kartu
// drží a jaké soubory měnil, co ji blokuje a na co se ptá, z čeho vychází, pravidla, zdroj a realizace.
// Pořadí je pevné; stav všech těchto věcí nese proces a stavová věta nad bloky, tady jsou jen detaily.
import type { ReactNode } from "react";
import CardEvidence, { type CompletionEvidence } from "./CardEvidence";
import CardChecks from "./CardChecks";
import CardLease from "./CardLease";
import CardUpstream from "./CardUpstream";
import InheritedRules from "./InheritedRules";
import CardRules from "./CardRules";
import CardSource from "./CardSource";
import SourceRealization from "./SourceRealization";
import { WorkDetails } from "./WorkNow";
import type { NodeCardData } from "./NodeCard";
import type { CardActions } from "../logic/card-actions";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="node-card__section">
      <h4 className="node-card__section-title">{title}</h4>
      {children}
    </section>
  );
}

export default function CardDetails({ id, data, actions, release, realize }: {
  id: string;
  data: NodeCardData;
  actions: CardActions;
  release?: () => Promise<unknown>;
  realize: (commit: string, prUrl: string) => Promise<void>;
}) {
  const { view, blocks } = data;
  const evidence: CompletionEvidence | undefined = data.evidence;
  const asks = data.work?.waitingOnHuman.length ? data.work.waitingOnHuman : data.frontier?.waitingOnHuman ?? [];
  const blockers = data.work?.blockedBy.length ? data.work.blockedBy : data.frontier?.blockedBy ?? [];
  const showRules = !!data.inheritedRules?.length || !!data.rules?.items.length;
  return (
    <details className="nodrag nopan node-card__fold node-card__details">
      <summary>Podrobnosti</summary>
      <Section title="Doklady">
        <CardEvidence evidence={evidence} autonomous={data.autonomous} />
        <CardChecks checks={view.checks} goal_mode={view.goal_mode} evidence={evidence} />
      </Section>
      {(data.work || data.lease) && (
        <Section title="Práce">
          {data.work && <WorkDetails row={data.work} />}
          {data.lease && <CardLease lease={data.lease} release={release} />}
        </Section>
      )}
      {(asks.length > 0 || blockers.length > 0 || data.frontier?.claim) && (
        <Section title="Proč karta stojí">
          {data.frontier?.claim && <p>{data.frontier.claim}</p>}
          {blockers.length > 0 && <p>Blokuje: {blockers.map((b) => b.name || b.id).join(", ")}</p>}
          {asks.map((ask) => <p key={ask.blockId}>Otázka na tebe: {ask.ask}</p>)}
        </Section>
      )}
      {!!data.upstream?.rows.length && (
        <Section title="Vychází z"><CardUpstream rows={data.upstream.rows} open={actions.open} /></Section>
      )}
      {showRules && (
        <Section title="Pravidla">
          {!!data.inheritedRules?.length && <InheritedRules rules={data.inheritedRules} />}
          {!!data.rules?.items.length && <CardRules rules={data.rules.items} write={actions.ruleWrite} review={actions.ruleReview} disabled={blocks.disabled} />}
        </Section>
      )}
      {(data.source || data.realization) && (
        <Section title="Zdroj">
          {data.source && <CardSource key={JSON.stringify(data.source)} {...data.source} />}
          {data.realization && (
            <SourceRealization key={JSON.stringify(data.realization.value)} nodeId={id} {...data.realization} save={realize}
              mergePassed={evidence?.merge.status === "passed"} />
          )}
        </Section>
      )}
    </details>
  );
}
