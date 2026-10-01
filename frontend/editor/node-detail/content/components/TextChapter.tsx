// Jedna kapitola stránky Text = jedna karta vrstvy. Hlavička se při čtení lepí nahoru a nese stav karty:
// šipku rozbalení, druh a název, kdo psal do paměti a kolik, co čeká v komunikaci (jen s načteným
// briefem), zámek uzavřené karty, čas poslední změny a cestu dovnitř (Zanořit). Tělo dostává dílek
// hotové od rodiče (`children`, editor textu). Rodič ho připojí až při prvním rozbalení a pak už ho
// nechá připojené; sbalení tělo jen skryje (`hidden`), protože editor při odpojení neuloží rozepsaný text.
import type { ReactNode } from "react";
import { READ_ONLY_TEXT, type OverviewModel } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import { relativeTime, workStateOf, type ChapterWork } from "@/editor/node-detail/agent-summary/logic/agent-summary";
import CommsChips from "@/editor/node-detail/agent-summary/components/CommsChips";
import MemoryDots from "@/editor/node-detail/agent-summary/components/MemoryDots";
import WorkChip from "@/editor/node-detail/agent-summary/components/WorkChip";
import Icon from "@/ui-kit/icon/components/Icon";
import type { CanvasNode } from "@/shared/types/logic/types";
import "@/editor/node-detail/content/styles/text-workspace.css";

const KIND_LABEL: Record<CanvasNode["kind"], string> = { node: "Uzel", sector: "Sektor", area: "Oblast", comment: "Komentář" };

export default function TextChapter({
  node, expanded, highlighted, hovered, work, overview, closed, now, onToggle, onHover, onEnter, children,
}: {
  node: CanvasNode;
  expanded: boolean;
  /** Krátké zvýraznění po skoku ze souhrnu. */
  highlighted: boolean;
  /** Myš stojí nad řádkem této karty v souhrnu (nebo nad kapitolou samotnou). */
  hovered: boolean;
  /** Levný souhrn paměti; `null` = karta ho nemá (komentář) nebo ještě nepřišel. */
  work: ChapterWork | null;
  /** Přehled z načteného briefu; `null` = brief se nenačetl, komunikace se nekreslí. */
  overview: OverviewModel | null;
  closed: boolean;
  now: Date;
  onToggle: (id: string) => void;
  onHover: (id: string | null) => void;
  onEnter: (id: string) => void;
  children?: ReactNode;
}) {
  const bodyId = `text-chapter-${node.id}-body`;
  const className = "text-block" +
    (expanded ? " text-block--expanded" : "") +
    (highlighted ? " text-block--highlighted" : "") +
    (hovered ? " text-block--hovered" : "");
  return (
    <article
      className={className}
      data-testid="text-block"
      data-node-id={node.id}
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
    >
      <header className="text-block__head">
        <h3 className="text-block__title">
          <button
            type="button"
            className="text-block__toggle"
            aria-expanded={expanded}
            aria-controls={bodyId}
            onClick={() => onToggle(node.id)}
          >
            <Icon name={expanded ? "chevron-down" : "chevron-right"} size={16} className="text-block__chevron" />
            <span className="text-block__kind">{KIND_LABEL[node.kind]}</span>
            <span className="text-block__name">{node.name}</span>
          </button>
        </h3>
        {work && (
          <span className="text-block__status">
            <WorkChip state={workStateOf(work)} />
            <MemoryDots filled={work.filled} />
          </span>
        )}
        {overview && <CommsChips communication={overview.communication} />}
        {closed && (
          <span className="text-block__lock" title={READ_ONLY_TEXT.closed}>
            <Icon name="lock" size={16} label={READ_ONLY_TEXT.closed} />
          </span>
        )}
        {work?.updatedAt && <span className="text-block__time">{relativeTime(work.updatedAt, now)}</span>}
        <button type="button" className="text-block__enter" onClick={() => onEnter(node.id)}>
          Zanořit
        </button>
      </header>
      <div className="text-block__body" id={bodyId} hidden={!expanded}>
        {children}
      </div>
    </article>
  );
}
