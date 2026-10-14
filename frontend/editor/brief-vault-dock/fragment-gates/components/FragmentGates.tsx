// Brány cyklu v detailu fragmentu, jen zobrazení (docs/schranka-neurony.md §3, §6, §9 body 8, 9): osm bran
// s payloadem a autorem (kdo navrhl, kdo potvrdil), predikční chyba u Ověřeno, slepá ulička s důvodem,
// zneplatnění, stav fronty agentů (`GET /api/brief-vault/next`) a poučení disciplíny. Schránku řídí agenti
// přes API, proto tu není žádný přepínač ani formulář. Rodič (BriefVaultDock) dodá načtený detail.
import type { FragmentDetail } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { useVaultGet, type VaultScope } from "../../logic/vault-actions";
import { deadEndReason, gateRows, queueText, type NextWork } from "../logic/gate-view";
import GateRow from "./GateRow";
import DisciplineLessons from "./DisciplineLessons";
import "../styles/fragment-gates.css";

export default function FragmentGates({ scope, detail }: { scope: VaultScope; detail: FragmentDetail }) {
  const id = detail.fragment.id;
  const discipline = detail.effectiveDiscipline ?? null;
  const next = useVaultGet<NextWork>(discipline ? "/api/brief-vault/next?" + new URLSearchParams({ ...scope, discipline }) : null, detail).data;
  // Návrh čekající na potvrzení zná jen fronta, a jen u fragmentu, který je v ní první.
  const queued = next?.fragment?.id === id && next.gate && next.proposal ? { gate: next.gate, proposal: next.proposal } : null;
  const reason = detail.deadEnd ? deadEndReason(detail) : "";
  return (
    <section className="fragment-gates" aria-label="Brány cyklu" data-testid="fragment-gates">
      <h5 className="fragment-gates__title">Brány cyklu · {detail.gateStep ?? 0}/8</h5>
      {detail.deadEnd && <p className="fragment-gates__dead" role="status">Slepá ulička (rozhodnuto: ne){reason ? `: ${reason}` : "."} Fronta agentů ji přeskakuje.</p>}
      {detail.gatesStale && <p className="fragment-gates__stale" role="status">Část bran byla zapnutá pro jiný název, text nebo disciplínu; platí znovu od první zneplatněné.</p>}
      <ol className="fragment-gates__list">
        {gateRows(detail).map((row) => (
          <li key={row.gate}><GateRow row={row} proposal={queued?.gate === row.gate ? queued.proposal : undefined} /></li>
        ))}
      </ol>
      {next && <p className="fragment-gates__queue" role="status">{queueText(next, id)}</p>}
      {discipline && <DisciplineLessons scope={scope} discipline={discipline} />}
    </section>
  );
}
