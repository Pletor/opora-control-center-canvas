import { useEffect, useState } from "react";
import type { DesktopState } from "@/shared/desktop-state/logic/types";

/** Předvolby délky svěřené autonomie: jeden klik = souhlas do daného času (server dovolí nejvýš 30 dní). */
export const AUTONOMY_PRESETS: { label: string; hours: number }[] = [
  { label: "1 h", hours: 1 }, { label: "8 h", hours: 8 }, { label: "24 h", hours: 24 }, { label: "3 dny", hours: 72 }, { label: "7 dní", hours: 168 },
];

/** Konec souhlasu od `now` o `hours` hodin, jako ISO čas se zónou pro /api/desktop-v3/autonomy. */
export function autonomyUntil(now: number, hours: number): string {
  return new Date(now + hours * 3_600_000).toISOString();
}

// Autonomie sektoru jako čip lišty: stav na první pohled, zapnutí jedním klikem na předvolbu, vypnutí jedním klikem.
// Souhlas uděluje člověk v UI; jméno a poznámka nejsou podmínka.
export default function SectorAutonomy({ sectorId, name, grant, disabled, save }: {
  sectorId: string; name: string; grant?: NonNullable<DesktopState["autonomy"]>[string]; disabled: boolean;
  save: (until: string, grantedBy: string, note: string) => Promise<void>;
}) {
  const [clock, setClock] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 30_000); return () => clearInterval(timer); }, []);
  const active = !!grant && Date.parse(grant.until) > clock;
  async function commit(until: string) {
    setError("");
    setBusy(true);
    try { await save(until, grant?.grantedBy || "člověk (UI)", ""); setClock(Date.now()); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <details className="board-bar__pop" data-testid={"sector-autonomy-" + sectorId}>
    <summary className={"board-bar__chip" + (active ? " board-bar__chip--on" : "")}>
      🤖 Autonomie: {active ? `do ${new Date(grant!.until).toLocaleString([], { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}` : grant ? "vypršela" : "vypnuto"}{busy ? " · ukládám…" : ""}
    </summary>
    <div className="board-bar__panel">
      <p>Agent smí v sektoru <b>{name}</b> sám uzavřít kartu s důkazy a hotovou pipeline. Bránu sektoru potvrzuje vždy člověk.</p>
      <div className="board-bar__presets" role="group" aria-label="Zapnout autonomii na">
        {AUTONOMY_PRESETS.map(preset => (
          <button key={preset.label} type="button" disabled={disabled || busy} onClick={() => void commit(autonomyUntil(Date.now(), preset.hours))}>{preset.label}</button>
        ))}
      </div>
      {grant && <button type="button" className="board-bar__off" disabled={disabled || busy} onClick={() => void commit("")}>Vypnout autonomii</button>}
      {grant && <p className="board-bar__muted">Udělil: {grant.grantedBy || "neuvedeno"}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  </details>;
}
