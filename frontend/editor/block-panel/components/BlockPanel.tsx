// Boční menu vybraného bloku nebo karty (panel karty) = stopa práce karty (docs/navrhy/2026-10-31-panel-bloku.md, varianta 1a
// s relacemi a logem v jedné ose). Rodič skládá dílky shora dolů: hlavička, práce na kartě, úsudek (jen
// s příznakem), stopa práce a port. Panel jen čte; odpověď srdci a odkazy do detailu karty hlásí nahoru.
import type { CardTab } from "@/hub/oporahub-card-drawer/open";
import type { TrailJudgment } from "../logic/card-trail";
import type { PanelView } from "../logic/panel-view";
import PanelHead from "./PanelHead";
import WorkSection from "./WorkSection";
import JudgmentSection from "./JudgmentSection";
import TrailSection from "./TrailSection";
import PortSection from "./PortSection";
import "../styles/block-panel.css";

export type BlockPanelProps = PanelView & {
  /** Stopa se ještě čte (první načtení) nebo se nepodařila. */
  loading: boolean;
  error: string;
  onOpenCard: (tab: CardTab) => void;
  onAnswerHeart: (item: TrailJudgment, text: string) => Promise<boolean>;
  /** Zavřít panel (× v hlavičce); výběr se vrátí na kartu. */
  onClose?: () => void;
};

export default function BlockPanel(props: BlockPanelProps) {
  return (
    <div className="block-panel" aria-label={props.head.kind === "card" ? `Stopa práce karty ${props.head.title}` : `Stopa práce bloku ${props.head.number}`}
      data-oh-block-panel={props.head.kind === "block" ? props.head.id : undefined} data-oh-card-panel={props.head.kind === "card" ? props.head.id : undefined}>
      <PanelHead head={props.head} onClose={props.onClose} />
      {props.error && <p className="block-panel__error" role="alert">{props.error}</p>}
      {props.loading && !props.error && <p className="block-panel__empty" role="status">Načítám stopu práce…</p>}
      <WorkSection work={props.work} live={props.live} />
      <JudgmentSection items={props.judgments} views={props.judgmentViews} onAnswer={props.onAnswerHeart} onOpen={props.onOpenCard} />
      <TrailSection groups={props.timeline} filesKnown={props.filesKnown} onHistory={() => props.onOpenCard("history")}
        onRuns={() => props.onOpenCard("run")} />
      <PortSection ports={props.ports} incoming={props.incoming} />
    </div>
  );
}
