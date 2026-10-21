import type { ProposalReviewModels } from "../logic/use-proposal-review-models";
import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import { blockedReasonLabel } from "../logic/review-labels";

export default function AcceptanceOverview({ model, open }: { model?: ProposalReviewModels; open: (target: DetailTarget) => void }) {
  const policy = model?.policy;
  const observed = [model?.spec, model?.graph, model?.content].filter(item => item?.context && !item.busy && !item.error);
  return <section className="oporahub-overview__panel"><header><h2>Přijetí návrhů plánu</h2><span>{!policy || policy.busy || policy.error || !policy.context ? "Pravidla nedoložena" : policy.context.policy?.enabled ? "Pravidla aktivní" : "Dosavadní lidské přijetí"}</span></header>
    <p className="oporahub-overview__empty">Riziko, připomínky a výslovné potvrzení patří přesnému návrhu. Pravidla GitHub PR review jsou samostatná.</p>
    {observed.map(item => item!.context!.blockedReasons.length > 0 && <div className="oporahub-overview__empty" key={item!.context!.proposalId}>
      <button type="button" onClick={() => open({ kind: item!.target.proposalKind === "spec" ? "changes" : item!.target.proposalKind === "content" ? "content" : "graph", id: item!.target.proposalId, title: "Návrh čeká na review" })}>Návrh {item!.target.proposalId.slice(0, 12)} čeká</button>
      <ul>{item!.context!.blockedReasons.map(reason => <li key={reason}>{blockedReasonLabel(reason)}</li>)}</ul></div>)}
    <button type="button" className="oporahub-overview__more" onClick={() => open({ kind: "acceptance-policy", title: "Pravidla přijetí plánů" })}>Pravidla přijetí plánů</button>
  </section>;
}
