// Hlavička Kanceláře: kolik pracovníků brány právě drží ticket a co dělá srdce (pracuje / spí, zprávy ve frontě).
import type { HeartStatus } from "@/layout/heart-channel/logic/heart-api";

type Props = {
  /** Stav srdce z `GET /api/brain/heart/status`; `null`, dokud stav není znám. */
  status: HeartStatus | null;
  workers: number;
};

function heartWord(status: HeartStatus | null): string {
  if (!status) return "srdce ?";
  if (!status.enabled) return "srdce vypnuté";
  return status.running ? "srdce pracuje" : "srdce spí";
}

export default function OfficeHeader({ status, workers }: Props) {
  const pending = status?.pending ?? 0;
  return (
    <header className="office-header">
      <h2 className="office-header__title">Kancelář</h2>
      <span className="office-header__workers">Pracovníci: {workers}</span>
      <span className={"office-header__occupancy" + (status?.running ? " office-header__occupancy--busy" : "")}
        title="Stav srdce projektu a počet zpráv, které na něj čekají">
        {heartWord(status)}{pending > 0 ? ` · ve frontě ${pending}` : ""}
      </span>
    </header>
  );
}
