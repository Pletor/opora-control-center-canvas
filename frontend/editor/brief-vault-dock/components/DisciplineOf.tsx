// Disciplína fragmentu v jeho detailu, jen zobrazení: skupina, disciplína a zda je vlastní, nebo zděděná po předkovi.
// Přeřazuje agent přes API (`op: set-discipline`); přeřazení zneplatní brány podstromu (jiný otisk vstupů).
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { UNASSIGNED, disciplineLabel, groupLabel, viewOf } from "../logic/disciplines";

export default function DisciplineOf({ fragment }: { fragment: VaultNode | undefined }) {
  if (!fragment) return null;
  const view = viewOf(fragment);
  const text = view === UNASSIGNED ? "nezařazené (bez disciplíny na celé cestě ke kořeni)"
    : `${groupLabel(view)} · ${disciplineLabel(view)} · ${fragment.discipline != null ? "vlastní" : "zděděná"}`;
  return (
    <div className="vault-actions vault-dock__discipline-of" data-testid="vault-fragment-discipline">
      <span className="vault-pill">Disciplína: {text}</span>
    </div>
  );
}
