import { useState } from "react";
import type { ApplicationSite, CanvasNode, CustomerJourney } from "@/shared/types/logic/types";
import { productFingerprint, type ProductDraft } from "@/project/product-tree/logic/product-tree";
import { useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import { journeyForSave, journeysForSave, newJourney, removeJourney, replaceJourney } from "../logic/journeys";
import { derivedForDomain, type DerivedJourney } from "../logic/derived-journeys";
import JourneyFunnel from "./JourneyFunnel";
import JourneyFunnelEditor from "./JourneyFunnelEditor";

/** Cesty zákazníka celé domény jako trychtýře stránek: v klidu každá cesta svým trychtýřem, „Upravit“ otevře editor
 * jedné cesty na jejím místě, „+ Přidat cestu“ novou na konci. Vazby mezi kroky odvodí backend (`derived`, hotová data
 * od rodiče). Ukládá rodič přes `onSave` celé `site` domény (stejně jako formulář domény, otisk hlídá souběžnou změnu). */
export default function CustomerJourneys({ domain, site: saved, pages, derived, disabled, onSave }: {
  domain: CanvasNode; site: ApplicationSite; pages: CanvasNode[]; derived: DerivedJourney[] | null; disabled: boolean; onSave: (draft: ProductDraft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<CustomerJourney | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const journeys = saved.journeys ?? [];
  const original = draft ? journeys.find((journey) => journey.id === draft.id) ?? null : null;
  useScopedSaveParticipant({ id: "architecture-journeys:" + domain.id, label: "Cesta zákazníka",
    dirty: draft !== null && JSON.stringify(journeyForSave(draft)) !== JSON.stringify(original), pending: saving,
    blocked: "Nejprve uložte nebo zrušte úpravu cesty zákazníka." });
  const derivedById = derivedForDomain(derived ?? [], domain.id);
  const fresh = newJourney(saved, pages.map((page) => page.id));
  async function save(site: ApplicationSite) {
    setSaving(true); setError("");
    try {
      await onSave({ id: domain.id, original: productFingerprint(domain), parentId: domain.parentId, name: domain.name, purpose: domain.purpose, site: journeysForSave(site) });
      setDraft(null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  }
  const editor = (journey: CustomerJourney) => <JourneyFunnelEditor key={journey.id} journey={journey} pages={pages} isNew={original === null}
    disabled={disabled || saving} saving={saving} error={error} onChange={setDraft} onSave={() => void save(replaceJourney(saved, journeyForSave(journey)))}
    onCancel={() => { setDraft(null); setError(""); }} onRemove={() => void save(removeJourney(saved, journey.id))}/>;
  return <section className="domain-map__journeys" data-testid="architecture-journeys">
    <header className="domain-map__journeys-head">
      <h3 className="domain-map__list-title">Cesty zákazníka</h3>
      {!draft && <button type="button" className="domain-map__section-add" disabled={disabled || !fresh} data-testid="architecture-journey-add" onClick={() => fresh && setDraft(fresh)}>+ Přidat cestu</button>}
    </header>
    {journeys.length || draft
      ? <ol className="domain-map__journey-list">
          {journeys.map((journey) => draft?.id === journey.id ? editor(draft)
            : <JourneyFunnel key={journey.id} journey={journey} pages={pages} derived={derivedById.get(journey.id)} disabled={disabled || draft !== null} onEdit={() => setDraft(structuredClone(journey))}/>)}
          {draft && original === null && editor(draft)}
        </ol>
      : <p className="domain-map__empty">{pages.length ? "Zatím bez cest. Cesta je trychtýř stránek: kudy zákazník jde, co na každé stránce zažívá a kolik lidí dojde dál." : "Cesty půjdou zadat, až doména bude mít stránky."}</p>}
  </section>;
}
