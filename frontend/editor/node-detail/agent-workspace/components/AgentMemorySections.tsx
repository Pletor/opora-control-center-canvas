// Pět polí paměti karty (rámec, postup, co se nepovedlo, úspěšné opravy, předávka). Dílek nic
// nenačítá ani neukládá: text dostává v props a každou změnu i opuštění pole hlásí nahoru rodiči
// (AgentWorkspace), který jediný drží revizi a zápis. Kreslí se dvěma způsoby podle toho, kolik má
// místa: v inspektoru („stack“) je pět složených řádků pod sebou, na ploše Agenti („segments“) pět
// stejně širokých pojmenovaných sloupců, jejichž rozbalení řídí deska pro celou aplikaci.
import {
  MAX_SECTION,
  SECTIONS,
  sectionLink,
  type AgentWorkspaceSections,
  type SectionKey,
} from "@/editor/node-detail/agent-workspace/logic/agent-workspace";
import { sectionIndicator } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import AgentSegment from "@/editor/node-detail/agent-workspace/segments/components/AgentSegment";
import { SEGMENTS } from "@/editor/node-detail/agent-workspace/segments/logic/agent-segments";
import "@/editor/node-detail/agent-workspace/styles/agent-workspace.css";

const MEMORY_SEGMENTS = SEGMENTS.filter((segment) => segment.area === "memory");

export type MemorySectionsProps = {
  nodeId: string;
  drafts: AgentWorkspaceSections;
  open: Record<SectionKey, boolean>;
  disabled: boolean;
  /** Která sekce má právě zkopírovaný odkaz; popisek tlačítka se na chvíli změní. */
  copied: SectionKey | null;
  onEdit: (key: SectionKey, value: string) => void;
  onBlur: (key: SectionKey) => void;
  onCopyLink: (key: SectionKey) => void;
  onToggle: (key: SectionKey, open: boolean) => void;
  layout?: "stack" | "segments";
};

export default function AgentMemorySections(props: MemorySectionsProps) {
  const { nodeId, drafts, open, disabled, copied, onEdit, onBlur, onCopyLink, onToggle, layout = "stack" } = props;

  /** Nápověda s tichým „Kopírovat odkaz“ a samotné pole; stejné v obou rozloženích. */
  function body(key: SectionKey, label: string, hint: string) {
    return <>
      <div className="agent-workspace__section-head">
        <p className="agent-workspace__hint">{hint}</p>
        <button
          type="button"
          className="nodrag agent-workspace__copy"
          title={sectionLink(nodeId, key)}
          onClick={() => onCopyLink(key)}
        >
          {copied === key ? "Zkopírováno" : "Kopírovat odkaz"}
        </button>
      </div>
      <textarea
        id={`agent-workspace-${nodeId}-${key}`}
        className="agent-workspace__input"
        aria-label={label}
        rows={4}
        maxLength={MAX_SECTION}
        value={drafts[key]}
        readOnly={disabled}
        onChange={(event) => onEdit(key, event.target.value)}
        onBlur={() => onBlur(key)}
      />
    </>;
  }

  if (layout === "segments") {
    return <>
      {MEMORY_SEGMENTS.map((segment) => {
        const key = segment.id as SectionKey;
        const hint = SECTIONS.find((section) => section.key === key)?.hint ?? "";
        return (
          <AgentSegment
            key={key}
            nodeId={nodeId}
            segment={segment}
            open={open[key]}
            onToggle={(isOpen) => onToggle(key, isOpen)}
          >
            <p className={"agent-workspace__indicator" + (drafts[key].trim() ? "" : " agent-workspace__indicator--empty")}>
              {sectionIndicator(drafts[key])}
            </p>
            {body(key, segment.title, hint)}
          </AgentSegment>
        );
      })}
    </>;
  }

  return <>
    {SECTIONS.map(({ key, label, hint }) => (
      <details
        className="agent-workspace__section"
        key={key}
        open={open[key]}
        onToggle={(event) => {
          // Hodnotu přečíst hned: v updateru je currentTarget už null (toggle přijde i při mountu otevřené sekce).
          onToggle(key, event.currentTarget.open);
        }}
      >
        <summary className="agent-workspace__summary">
          <span className="agent-workspace__label">{label}</span>
          <span className={"agent-workspace__indicator" + (drafts[key].trim() ? "" : " agent-workspace__indicator--empty")}>
            {sectionIndicator(drafts[key])}
          </span>
        </summary>
        {body(key, label, hint)}
      </details>
    ))}
  </>;
}
