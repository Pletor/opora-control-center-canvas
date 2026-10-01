// Legenda pod tabulkou: každá značka souhrnu jednou a slovy, ve stejné barvě jako v řádku. Kdo tabulku
// vidí poprvé, nemusí hádat, co znamenají přesýpací hodiny nebo pomlčka.
import WorkChip from "@/editor/node-detail/agent-summary/components/WorkChip";
import MemoryDots from "@/editor/node-detail/agent-summary/components/MemoryDots";
import Icon from "@/ui-kit/icon/components/Icon";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";
import "@/editor/node-detail/agent-summary/styles/agent-summary.css";

const MARKS: { icon: IconName; tone: string; text: string }[] = [
  { icon: "hourglass", tone: "pending", text: "čeká na potvrzení" },
  { icon: "circle-help", tone: "clarify", text: "potřebuje upřesnit" },
  { icon: "mail", tone: "question", text: "otevřené otázky" },
  { icon: "lock", tone: "lock", text: "zámek (popisek říká proč)" },
];

export default function AgentSummaryLegend() {
  return (
    <footer className="agent-summary__legend" aria-label="Legenda souhrnu">
      <span className="agent-summary__legend-item"><WorkChip state="agent" /> píše agent</span>
      <span className="agent-summary__legend-item"><WorkChip state="human" /> píše člověk</span>
      <span className="agent-summary__legend-item"><WorkChip state="empty" /> paměť prázdná</span>
      <span className="agent-summary__legend-item"><MemoryDots filled={2} /> paměť: pět polí karty</span>
      {MARKS.map((mark) => (
        <span key={mark.icon} className="agent-summary__legend-item">
          <span className={`agent-summary__legend-mark agent-summary__legend-mark--${mark.tone}`}><Icon name={mark.icon} size={16} /></span>
          {mark.text}
        </span>
      ))}
      <span className="agent-summary__legend-item">
        <span className="agent-summary__check agent-summary__check--present">✓</span> přítomno
        <span className="agent-summary__check agent-summary__check--missing">–</span> chybí
      </span>
      <span className="agent-summary__legend-item"><span className="agent-summary__missing">–</span> údaj karta zatím nemá</span>
    </footer>
  );
}
