// Co v komunikaci karty čeká na člověka: přesýpací hodiny = zpráva bez potvrzení převzetí, otazník =
// žádost o upřesnění, obálka = otevřená otázka. Nula se nekreslí, aby klidná karta nevypadala jako
// fronta práce. Nedostupná komunikace není nula, ale neznámo — proto „–“. Data přicházejí hotová z
// briefu (rodič rozhodne, jestli je načtený); dílek nic nenačítá.
import type { OverviewModel } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import Icon from "@/ui-kit/icon/components/Icon";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";
import "@/editor/node-detail/agent-summary/styles/agent-summary.css";

type Communication = OverviewModel["communication"];

const CHIPS: { key: "awaitingReceipt" | "needsClarification" | "openQuestions"; icon: IconName; tone: string; title: string }[] = [
  { key: "awaitingReceipt", icon: "hourglass", tone: "pending", title: "Čeká na potvrzení převzetí" },
  { key: "needsClarification", icon: "circle-help", tone: "clarify", title: "Potřebuje upřesnit" },
  { key: "openQuestions", icon: "mail", tone: "question", title: "Otevřené otázky" },
];

/** `emptyLabel`: co napsat, když nic nečeká (řádek souhrnu). Bez něj klidná karta nekreslí nic (hlavička kapitoly). */
export default function CommsChips({ communication, emptyLabel }: { communication: Communication; emptyLabel?: string }) {
  if (!communication.available) {
    return <span className="agent-summary__missing" title="Komunikace karty není dostupná.">–</span>;
  }
  const shown = CHIPS.filter((chip) => communication[chip.key] > 0);
  if (!shown.length && !communication.hasMore) {
    return emptyLabel ? <span className="agent-summary__none" title="Nic v komunikaci nečeká na člověka.">{emptyLabel}</span> : null;
  }
  return (
    <span className="agent-summary__comms" data-testid="comms-chips">
      {shown.map((chip) => (
        <span key={chip.key} className={`agent-summary__comm agent-summary__comm--${chip.tone}`} title={`${chip.title}: ${communication[chip.key]}`}>
          <Icon name={chip.icon} size={16} />
          {communication[chip.key]}
        </span>
      ))}
      {communication.hasMore && <span className="agent-summary__more" title="Starší zprávy zůstávají stránkované.">+</span>}
    </span>
  );
}
