import { useState } from "react";
import type { ApplicationSite, CanvasNode } from "@/shared/types/logic/types";
import { productFingerprint, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import { useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import { journeysForSave, journeyEndLabel } from "../logic/journeys";
import CustomerJourneysEditor from "./CustomerJourneysEditor";

/** Cesty zákazníka A → B celé domény: v klidu seznam „název: začátek → cíl“, po „Upravit cesty“ editor řádků.
 * Kroky mezi začátkem a cílem nezadává nikdo, odvodí je stroj z vazeb. Ukládá rodič přes `onSave` (stejně jako formulář domény). */
export default function CustomerJourneys({ domain, site: saved, pages, disabled, onSave }: {
  domain: CanvasNode; site: ApplicationSite; pages: CanvasNode[]; disabled: boolean; onSave: (draft: ProductDraft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<ApplicationSite | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useScopedSaveParticipant({ id: "architecture-journeys:" + domain.id, label: "Cesty zákazníka",
    dirty: draft !== null && JSON.stringify(journeysForSave(draft)) !== JSON.stringify(saved), pending: saving,
    blocked: "Nejprve uložte nebo zrušte úpravu cest zákazníka." });
  const journeys = saved.journeys ?? [];
  async function save(site: ApplicationSite) {
    setSaving(true); setError("");
    try {
      await onSave({ id: domain.id, original: productFingerprint(domain), parentId: domain.parentId, name: domain.name, purpose: domain.purpose, site: journeysForSave(site) });
      setDraft(null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  }
  const end = (id: string) => {
    const { label, missing } = journeyEndLabel(id, pages);
    return <span className={"domain-map__journey-end" + (missing ? " domain-map__journey-end--missing" : "")}>{label}</span>;
  };
  return <section className="domain-map__journeys" data-testid="architecture-journeys">
    <header className="domain-map__journeys-head">
      <h3 className="domain-map__list-title">Cesty zákazníka A → B</h3>
      {!draft && <button type="button" className="domain-map__section-add" disabled={disabled || !pages.length} data-testid="architecture-journeys-edit" onClick={() => setDraft(structuredClone(saved))}>Upravit cesty</button>}
    </header>
    {draft
      ? <CustomerJourneysEditor site={draft} pages={pages} disabled={disabled || saving} saving={saving} error={error} onChange={setDraft}
          onSave={() => void save(draft)} onCancel={() => { setDraft(null); setError(""); }}/>
      : journeys.length
        ? <ol className="domain-map__journey-list">{journeys.map((journey) => <li key={journey.id} className="domain-map__journey" data-testid={"architecture-journey-" + journey.id}>
            <strong>{journey.name}</strong>{end(journey.from)}<span aria-hidden="true" className="domain-map__journey-arrow">→</span>{end(journey.to)}
          </li>)}</ol>
        : <p className="domain-map__empty">{pages.length ? "Zatím bez cest. Cesta říká, odkud kam má zákazník dojít; je zároveň zadáním i testem." : "Cesty půjdou zadat, až doména bude mít stránky."}</p>}
  </section>;
}
