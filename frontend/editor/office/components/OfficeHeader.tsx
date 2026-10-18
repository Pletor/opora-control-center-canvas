// Hlavička Kanceláře: kolik relací čeká na člověka, skok na dalšího čekajícího a obsazenost procesů.
type Props = {
  waiting: number;
  /** Běžící procesy a limit z `GET /api/assistant/status`; `null`, dokud stav není znám. */
  running: number | null;
  limit: number | null;
  onNext: () => void;
};

export default function OfficeHeader({ waiting, running, limit, onNext }: Props) {
  const full = running !== null && limit !== null && running >= limit;
  return (
    <header className="office-header">
      <h2 className="office-header__title">Kancelář</h2>
      <span className={"office-header__waiting" + (waiting ? " office-header__waiting--on" : "")}>Čeká na tebe ({waiting})</span>
      <button type="button" className="office-header__next" onClick={onNext} disabled={!waiting}
        title={waiting ? "Otevřít v panelu asistenta nejstarší čekající relaci (opakovaně cyklí)" : "Nikdo nečeká na tvé schválení"}>
        Další čekající
      </button>
      <span className={"office-header__occupancy" + (full ? " office-header__occupancy--full" : "")} title="Běžící procesy asistenta / limit">
        běží {running ?? "?"} / {limit ?? "?"}
      </span>
    </header>
  );
}
