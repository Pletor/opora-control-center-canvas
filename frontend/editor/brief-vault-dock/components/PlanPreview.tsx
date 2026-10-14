// Náhled vložení karet ze schránky: plán struktury (oblast → sektor → karty) složí server z vybraných fragmentů
// a ověří ho dryRun (POST /api/brief-vault/plan, nic se nezapíše). Člověk vidí karty, bloky a nové oblasti
// a sektory a teprve jeho klik pošle tutéž dávku na /api/canvas-plan.
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { CanvasPlanResult } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { fetchPlan, previewOf, type ServerPlan } from "../logic/vault-plan-preview";
import type { VaultScope } from "../logic/vault-actions";

export default function PlanPreview({ scope, digest, fragmentIds, title, onApplied, onCancel }: {
  scope: VaultScope;
  digest: string;
  fragmentIds: string[];
  title: string;
  onApplied: (result: CanvasPlanResult, cards: number) => void;
  onCancel: () => void;
}) {
  const [plan, setPlan] = useState<ServerPlan | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const key = fragmentIds.join(",");
  useEffect(() => {
    let live = true;
    setPlan(null); setError("");
    fetchPlan(scope, fragmentIds)
      .then((result) => { if (live) setPlan(result); })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- výběr se porovnává podle id (key)
  }, [scope.project, scope.workspace, digest, key]);
  const preview = plan ? previewOf(plan) : null;
  async function write() {
    if (!plan || !preview) return;
    setBusy(true); setError("");
    try {
      const result = await api<CanvasPlanResult>("/api/canvas-plan", { ...scope, digest, plan: plan.plan });
      if (!result.ok || result.dryRun) throw new Error("Server dávku nepotvrdil.");
      onApplied(result, preview.cards.length);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const count = preview?.cards.length ?? 0;
  return (
    <section className="vault-panel" aria-label={"Náhled: " + title} data-testid="vault-plan-preview">
      <h3 className="vault-panel__title">{title}: náhled</h3>
      {preview && plan && (
        <>
          <p className="vault-panel__text">{count} karet · {preview.blocks} bloků · každá karta odkazuje na svůj fragment (fragmentRef) a nové karty mají stav draft.
            {preview.structure.length > 0 && ` Nově vznikne: ${preview.structure.join(", ")}.`}
            {plan.skipped > 0 && ` Dalších ${plan.skipped} se do jedné dávky nevejde; po vložení připrav návrh znovu.`}</p>
          <ol className="vault-plan__list">
            {preview.cards.map((card) => (
              <li key={card.ref}>{card.name}{card.blocks?.length ? ` — bloky: ${card.blocks.map((block) => block.title).join(", ")}` : ""}</li>
            ))}
          </ol>
          <p className="vault-dock__notice" role="status">Server dávku ověřil: {plan.summary || "bez výhrad"}. Zatím nic nezapsáno.</p>
        </>
      )}
      {!plan && !error && <p className="vault-dock__notice" role="status">Skládám plán na serveru (dryRun, nic se nezapíše)…</p>}
      {error && <p className="vault-dock__error" role="alert">{error}</p>}
      <div className="vault-actions">
        <button type="button" className="vault-button vault-button--primary" disabled={!plan || busy || !count}
          onClick={() => void write()}>Potvrdit a vložit {count} {count === 1 ? "kartu" : count > 1 && count < 5 ? "karty" : "karet"}</button>
        <button type="button" className="vault-button" disabled={busy} onClick={onCancel}>Zrušit</button>
      </div>
    </section>
  );
}
