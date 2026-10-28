import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { StudioCardView } from "../logic/card-view";
import StudioCardIcon from "./StudioCardIcon";
import GuardBadge from "../../studio-guards/components/GuardBadge";
import WorktreeBadge from "../../studio-worktree/components/WorktreeBadge";
import "../styles/studio-card.css";

export type StudioCardData = { view: StudioCardView; onEnter: (id: string) => void };
export type StudioCardNode = Node<StudioCardData, "studio-card">;

/** Karta jedné položky úrovně Studia v designu TechViz: hlavička s ikonou druhu, názvem a štítkem stavu, podtitulek
 * (cesta, role sekce, technologie), účel a pata se souhrnem dětí, odznakem „cíl z MODELu“, dírami („3 díry · 1 v práci“), nálezy strážců
 * a větví worktree. Karta, na které se pracuje ve worktree, má čárkovaný rám se seříznutým rohem (`--worktree`). Porty jsou body na
 * obvodu (vstup vlevo, výstup vpravo); vazby jen ukazují, netáhnou se. Dvojklik hlásí sestup rodiči (`onEnter`). */
export default function StudioCard({ data, selected }: NodeProps<StudioCardNode>) {
  const { view, onEnter } = data;
  return <article className={`studio-card studio-card--${view.state} studio-card--${view.kind}` + (view.worktree ? " studio-card--worktree" : "") + (selected ? " studio-card--selected" : "")}
    data-testid={"studio-card-" + view.id} data-worktree={view.worktree?.count ?? 0} aria-label={`${view.kindLabel} ${view.name}, ${view.stateLabel}` + (view.worktree ? ", pracuje se ve worktree" : "")} onDoubleClick={() => onEnter(view.id)}>
    <Handle type="target" position={Position.Left} isConnectable={false} className="studio-card__port studio-card__port--in" title="Vstup"/>
    <header className="studio-card__head">
      <span className="studio-card__icon"><StudioCardIcon name={view.icon}/></span>
      <strong className="studio-card__name" title={view.name}>{view.name}</strong>
      <span className="studio-card__state" data-testid={"studio-card-state-" + view.id}>{view.stateLabel}</span>
    </header>
    <div className="studio-card__body">
      <span className="studio-card__kind">{view.kindLabel}{view.subtitle && <code className="studio-card__subtitle">{view.subtitle}</code>}</span>
      <p className="studio-card__purpose">{view.purpose || "Bez účelu"}</p>
    </div>
    <footer className="studio-card__foot">
      <span className="studio-card__summary">{view.summary}</span>
      {view.modelTarget && <span className="studio-card__model" data-testid={"studio-card-model-" + view.id} title="Na kartu váže uzel MODELu: agent dostane jeho cíl (kapacita, odolnost) v briefu. Cíl, ne měření.">cíl z MODELu</span>}
      {view.holesText && <span className="studio-card__holes" title="Díry mapy pod touto kartou; „v práci“ = některý worktree je už zavírá">{view.holesText}</span>}
      <GuardBadge guards={view.guards} testId={"studio-card-guards-" + view.id}/>
      <WorktreeBadge worktree={view.worktree} testId={"studio-card-worktree-" + view.id}/>
      {view.children > 0 && <span className="studio-card__enter" aria-hidden="true">↳ {view.children}</span>}
    </footer>
    <Handle type="source" position={Position.Right} isConnectable={false} className="studio-card__port studio-card__port--out" title="Výstup"/>
  </article>;
}
