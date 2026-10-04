import type { CanvasNode } from "@/shared/types/logic/types";
import { DOMAIN_KIND_LABEL, domainKindOf } from "../logic/domain-kind";
import DomainKindIcon from "./DomainKindIcon";

/** One domain: icon of its kind, host, "kind · purpose", ID, link to its page map and a quiet Edit. */
export default function DomainCard({ node, tone, disabled, onOpen, onEdit, onSplit }: {
  node: CanvasNode; tone: "prod" | "dev" | "legacy"; disabled: boolean;
  onOpen: () => void; onEdit: () => void; onSplit: (host: string) => void;
}) {
  const environments = node.site?.kind === "application" ? node.site.environments : [];
  const kind = domainKindOf(node);
  const shared = environments.length > 1;
  return <article className={"arch-landing__card arch-landing__card--" + tone} data-testid={"architecture-domain-" + node.id}>
    <DomainKindIcon kind={kind}/>
    <h3 className="arch-landing__host">{environments[0]?.host || node.name}</h3>
    <p className="arch-landing__meta">{DOMAIN_KIND_LABEL[kind]} · {node.purpose || node.name}</p>
    {shared && environments.map((env) => <div className="arch-landing__env" key={env.host}>
      <code>{env.host}</code>
      <button type="button" className="arch-landing__quiet" disabled={disabled} onClick={() => onSplit(env.host)}>Oddělit doménu</button>
    </div>)}
    <small className="arch-landing__id">ID: {node.id}</small>
    <div className="arch-landing__actions">
      <button type="button" className="arch-landing__open" data-testid={"architecture-open-domain-" + node.id} onClick={onOpen}>Otevřít mapu projektu</button>
      <button type="button" className="arch-landing__quiet" disabled={disabled} onClick={onEdit}>Upravit</button>
    </div>
  </article>;
}
