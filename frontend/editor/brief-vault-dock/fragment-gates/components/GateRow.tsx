// Jedna brána v detailu fragmentu, jen zobrazení: tečka stavu, titulek, kdo bránu zapnul a kdy, uložený payload
// česky (u Ověřeno chyba předpovědi), u další brány na řadě čekající návrh s autorem a důvod, proč cyklus stojí.
import { formatError, GATE_TITLES } from "@/editor/node-detail/brief-vault/logic/gate-bar";
import { shortWhen } from "../../logic/vault-dock-model";
import { payloadLines, whoLabel, type GateRow as Row, type NextWork } from "../logic/gate-view";

export default function GateRow({ row, proposal }: { row: Row; proposal?: NextWork["proposal"] }) {
  const state = row.on ? "on" : row.stale ? "stale" : row.next ? "next" : "off";
  const entry = row.entry;
  const lines = payloadLines(row.on || row.stale ? entry?.payload : null);
  const error = row.gate === "verified" && row.on ? entry?.payload?.predictionError as number | undefined : undefined;
  const status = row.on ? `potvrdil ${whoLabel(entry?.by, entry?.actor)} · ${shortWhen(entry?.at ?? "")}`
    : row.stale ? `zneplatněno změnou vstupů (zapnul ${whoLabel(entry?.by, entry?.actor)})`
    : row.next ? (proposal ? "čeká na potvrzení návrhu" : "další na řadě, čeká na návrh") : "vypnuto";
  return (
    <div className={"fragment-gates__row fragment-gates__row--" + state} data-testid={"gate-" + row.gate}>
      <span className={"brief-gates__dot brief-gates__dot--" + state} aria-hidden="true" />
      <div className="fragment-gates__body">
        <div className="fragment-gates__head">
          <strong title={GATE_TITLES[row.gate].hint}>{row.title}</strong>
          <span className="fragment-gates__state">{status}</span>
          {error !== undefined && <span className="fragment-gates__error" title="Predikční chyba e = (testy + kola kritika + nečekané) / 3">chyba předpovědi {formatError(error)}</span>}
        </div>
        {lines.length > 0 && <ul className="fragment-gates__payload">{lines.map((line) => <li key={line}>{line}</li>)}</ul>}
        {proposal && (
          <div className="fragment-gates__proposal" aria-label="Návrh čekající na potvrzení">
            <span className="fragment-gates__state">navrhl {whoLabel(proposal.by, proposal.actor)} · {shortWhen(proposal.at)}{proposal.note ? ` · ${proposal.note}` : ""}</span>
            <ul className="fragment-gates__payload">{payloadLines(proposal.payload).map((line) => <li key={line}>{line}</li>)}</ul>
          </div>
        )}
        {row.waiting && <span className="fragment-gates__waiting">{row.waiting}</span>}
      </div>
    </div>
  );
}
