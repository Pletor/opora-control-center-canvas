// Náhled vložení karet ze schránky: koncept /api/canvas-plan se nejdřív ověří na serveru (dryRun, nic se
// nezapíše), člověk vidí karty, bloky a odkazy na fragmenty a teprve jeho klik dávku zapíše.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { CanvasPlanResult } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { planBody, type VaultPlan } from "../logic/vault-plan";
import type { VaultScope } from "../logic/vault-actions";

export default function PlanPreview({ scope, digest, plan, title, onApplied, onCancel }: {
  scope: VaultScope;
  digest: string;
  plan: VaultPlan;
  title: string;
  onApplied: (result: CanvasPlanResult) => void;
  onCancel: () => void;
}) {
  const [check, setCheck] = useState<{ summary: string } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    setCheck(null); setError("");
    api<CanvasPlanResult>("/api/canvas-plan", { ...scope, digest, dryRun: true, plan: planBody(plan) })
      .then((result) => { if (live) setCheck({ summary: result.summary }); })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; };
  }, [scope.project, scope.workspace, digest, plan]);
  async function write() {
    setBusy(true); setError("");
    try {
      const result = await api<CanvasPlanResult>("/api/canvas-plan", { ...scope, digest, plan: planBody(plan) });
      if (!result.ok || result.dryRun) throw new Error("Server dávku nepotvrdil.");
      onApplied(result);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const blocks = plan.cards.reduce((sum, card) => sum + card.blocks.length, 0);
  return (
    <section className="vault-panel" aria-label={"Náhled: " + title} data-testid="vault-plan-preview">
      <h3 className="vault-panel__title">{title}: náhled</h3>
      <p className="vault-panel__text">{plan.cards.length} karet · {blocks} bloků · každá karta odkazuje na svůj fragment (fragmentRef) a nové karty mají stav draft.
        {plan.skipped > 0 && ` Dalších ${plan.skipped} se do jedné dávky nevejde; po vložení připrav návrh znovu.`}</p>
      <ol className="vault-plan__list">
        {plan.cards.map((card) => (
          <li key={card.ref}>{card.name}{card.blocks.length ? ` — bloky: ${card.blocks.map((block) => block.title).join(", ")}` : ""}</li>
        ))}
      </ol>
      {!check && !error && <p className="vault-window__notice" role="status">Ověřuji dávku na serveru (dryRun, nic se nezapíše)…</p>}
      {check && <p className="vault-window__notice" role="status">Server dávku ověřil: {check.summary || "bez výhrad"}. Zatím nic nezapsáno.</p>}
      {error && <p className="vault-window__error" role="alert">{error}</p>}
      <div className="vault-actions">
        <button type="button" className="vault-button vault-button--primary" disabled={!check || busy || !plan.cards.length}
          onClick={() => void write()}>Potvrdit a vložit {plan.cards.length} {plan.cards.length === 1 ? "kartu" : plan.cards.length < 5 ? "karty" : "karet"}</button>
        <button type="button" className="vault-button" disabled={busy} onClick={onCancel}>Zrušit</button>
      </div>
    </section>
  );
}
