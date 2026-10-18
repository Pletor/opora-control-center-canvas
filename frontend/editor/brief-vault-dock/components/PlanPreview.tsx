// Náhled vložení karet ze schránky: plán struktury (oblast → sektor → karty) složí server z vybraných fragmentů
// a ověří ho dryRun (POST /api/brief-vault/plan, nic se nezapíše). Člověk vidí karty, bloky a nové oblasti
// a sektory a teprve jeho klik pošle tutéž dávku na /api/canvas-plan. Když server plán odmítne (409 s `fragments`:
// nezařazené fragmenty, chybějící mikrokrok …), dílek vypíše dotčené fragmenty po důvodech s „Otevřít fragment“
// (klik bublá přes onOpenFragment k rodiči, který přepne na Zadání a fragment otevře).
import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { trackSaveWrite } from "@/shared/hooks/logic/save-coordinator";
import type { CanvasPlanResult } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { fetchPlan, planBlocker, previewOf, type ServerPlan } from "../logic/vault-plan-preview";
import type { VaultScope } from "../logic/vault-actions";

export default function PlanPreview({ scope, digest, fragmentIds, title, onApplied, onCancel, onOpenFragment }: {
  scope: VaultScope;
  digest: string;
  fragmentIds: string[];
  title: string;
  onApplied: (result: CanvasPlanResult, cards: number) => void;
  onCancel: () => void;
  onOpenFragment: (id: string) => void;
}) {
  const [plan, setPlan] = useState<ServerPlan | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const key = fragmentIds.join(",");
  useEffect(() => {
    let live = true;
    setPlan(null); setError(null);
    fetchPlan(scope, fragmentIds)
      .then((result) => { if (live) setPlan(result); })
      .catch((e: unknown) => { if (live) setError(e ?? "Plán se nepodařilo načíst."); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- výběr se porovnává podle id (key)
  }, [scope.project, scope.workspace, digest, key]);
  const preview = plan ? previewOf(plan) : null;
  async function write() {
    if (!plan || !preview) return;
    setBusy(true); setError(null);
    try {
      // Vlastní zápis plátna: koordinátor ho zná, lišta verzí ho neukáže jako změnu mimo okno.
      const result = await trackSaveWrite(scope.project, scope.workspace, api<CanvasPlanResult>("/api/canvas-plan", { ...scope, digest, plan: plan.plan }));
      if (!result.ok || result.dryRun) throw new Error("Server dávku nepotvrdil.");
      onApplied(result, preview.cards.length);
    } catch (e: unknown) { setError(e ?? "Vložení se nezdařilo."); }
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
      {!plan && error === null && <p className="vault-dock__notice" role="status">Skládám plán na serveru (dryRun, nic se nezapíše)…</p>}
      {error !== null && <PlanError error={error} onOpenFragment={onOpenFragment} />}
      <div className="vault-actions">
        <button type="button" className="vault-button vault-button--primary" disabled={!plan || busy || !count}
          onClick={() => void write()}>Potvrdit a vložit {count} {count === 1 ? "kartu" : count > 1 && count < 5 ? "karty" : "karet"}</button>
        <button type="button" className="vault-button" disabled={busy} onClick={onCancel}>Zrušit</button>
      </div>
    </section>
  );
}

/** Odmítnutý plán: srozumitelné důvody a dotčené fragmenty k otevření; jiná chyba jako text serveru. */
function PlanError({ error, onOpenFragment }: { error: unknown; onOpenFragment: (id: string) => void }) {
  const blocker = planBlocker(error);
  if (!blocker) return <p className="vault-dock__error" role="alert">{error instanceof Error ? error.message : String(error)}</p>;
  return (
    <div className="vault-plan__blocked" role="alert" data-testid="vault-plan-blocked">
      <p className="vault-panel__text"><strong>Plán nejde složit.</strong></p>
      {blocker.groups.map((group) => (
        <div key={group.reason}>
          <p className="vault-panel__text">{group.text}</p>
          <ul className="vault-plan__list">
            {group.fragments.map((item) => (
              <li key={item.id} className="vault-plan__blocked-item">
                <span>{item.title}</span>
                <button type="button" className="vault-button" onClick={() => onOpenFragment(item.id)}>Otevřít fragment</button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
