import type { StopView } from "../logic/heart-explain";

/** Tabulka „Kde se může zastavit“: aktivní zarážky nahoře a výrazně, ať je vidět, co srdce drží právě teď. */
export default function HeartStops({ stops }: { stops: StopView[] }) {
  return (
    <table className="pletor-dashboard__table heart-explain__stops">
      <thead><tr><th>Zarážka</th><th>Stav</th><th>Proč</th><th>Čím uvolnit</th></tr></thead>
      <tbody>
        {stops.map((s) => (
          <tr key={s.id} className={s.active ? "heart-explain__stop heart-explain__stop--active" : "heart-explain__stop"}>
            <td>{s.label}</td><td>{s.active ? "drží" : "volno"}</td><td>{s.detail}</td><td>{s.lever}</td>
          </tr>
        ))}
        {stops.length === 0 && <tr><td colSpan={4} className="pletor-dashboard__empty">Žádné zarážky.</td></tr>}
      </tbody>
    </table>
  );
}
