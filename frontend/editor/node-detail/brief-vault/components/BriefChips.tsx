// Čipy „Ze schránky: 3.36 · 3.37 v1 ⚠ …“ v záložce Zadání: z kterých fragmentů karta vznikla a zda se
// fragment od vložení změnil. Jen zobrazení; data dodá rodič (fragmentRefs ze stavu karty + rejstřík stromu).
import { briefChips, type FragmentRef, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import "@/editor/node-detail/brief-vault/styles/brief-vault.css";

export default function BriefChips({ refs, index }: { refs: FragmentRef[] | undefined; index: Map<string, VaultNode> }) {
  const chips = briefChips(refs, index);
  if (!chips.length) return null;
  return (
    <div className="brief-vault__chips brief-vault__from" data-testid="brief-chips">
      <span className="brief-vault__from-label">Ze schránky:</span>
      {chips.map((chip) => (
        <span key={chip.fragmentId} className={"brief-chip" + (chip.changed ? " brief-chip--changed" : "")}
          title={chip.latestRevision == null ? "Fragment není ve schránce tohoto prostoru dostupný."
            : chip.changed ? `Zadání se změnilo: karta vznikla z r${chip.insertedRevision}, poslední je r${chip.latestRevision}.`
              : `Karta vznikla z r${chip.insertedRevision} (poslední revize).`}>
          {chip.title}{chip.changed ? ` v${chip.insertedRevision} ⚠` : ""}
        </span>
      ))}
    </div>
  );
}
