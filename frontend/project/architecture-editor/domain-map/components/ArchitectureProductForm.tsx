import { useEffect, useRef, useState } from "react";
import type { ProductDraft } from "@/project/product-tree/logic/product-tree";
import type { SitePlatform } from "@/shared/types/logic/types";
import { useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import { pageSiteForSave } from "../logic/page-site";
import { addressValue, applicationSiteForSave, isMobilePlatform, PLATFORM_CHOICES, withAddress, withPlatform } from "../logic/site-platform";
import PageIntentFields from "./PageIntentFields";
import PageJourneys from "./PageJourneys";
import type { PageJourneyRole } from "../logic/page-journeys";
import IntentButton, { type IntentEntry } from "@/project/intent-canvas/intent-entry/components/IntentButton";

/** Structural identity belongs to the domain map; working specifications stay in Editor.
 * `journeyRoles`: the customer journeys this page lies on, shown read-only (journeys are edited in the funnel).
 * `intent`: entry to the page intent canvas, offered only for an existing page. */
export default function ArchitectureProductForm({ initial, disabled, journeyRoles, intent, onSave, onClose }: {
  initial: ProductDraft; disabled: boolean; journeyRoles?: PageJourneyRole[]; intent?: IntentEntry; onSave: (draft: ProductDraft) => Promise<void>; onClose: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useScopedSaveParticipant({ id: `architecture-product-form:${initial.id ?? initial.parentId ?? "new-domain"}`,
    label: draft.site.kind === "page" ? "Formulář stránky" : "Formulář domény",
    dirty: JSON.stringify(draft) !== JSON.stringify(initial), pending: saving,
    blocked: "Nejprve potvrďte nebo zrušte tento formulář. Uložit vše nevytváří nové stránky ani domény." });
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { form.current?.scrollIntoView({ block: "nearest" }); form.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true }); }, []);
  const locked = disabled || saving;
  async function submit() {
    if (locked) return;
    setSaving(true); setError("");
    try {
      const site = draft.site.kind === "page" ? pageSiteForSave(draft.site) : applicationSiteForSave(draft.site);
      await onSave({ ...draft, site }); onClose();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  }
  return <form ref={form} className="ae-form ae-product-form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <h3>{draft.id ? "Upravit" : "Přidat"} {draft.site.kind === "page" ? "stránku" : "doménu"}</h3>
    <label>Název<input required maxLength={160} disabled={locked} data-testid="architecture-product-name" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })}/></label>
    <label>Účel<textarea rows={3} maxLength={4000} disabled={locked} data-testid="architecture-product-purpose" value={draft.purpose} onChange={(event) => setDraft({ ...draft, purpose: event.target.value })}/></label>
    {draft.site.kind === "application" && <label>Platforma<select value={draft.site.platform ?? "web"} disabled={locked} data-testid="architecture-product-platform"
      onChange={(event) => { if (draft.site.kind === "application") setDraft({ ...draft, site: withPlatform(draft.site, event.target.value as SitePlatform) }); }}>
      {PLATFORM_CHOICES.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select></label>}
    {draft.site.kind === "page" ? <PageIntentFields site={draft.site} disabled={locked} intent={draft.id && intent ? <IntentButton pageId={draft.id} entry={intent}/> : null} onChange={(site) => setDraft({ ...draft, site })}/> : draft.site.environments.map((env, index) => <fieldset key={index} disabled={locked}>
      <label>Prostředí<select value={env.name} data-testid="architecture-product-environment" onChange={(event) => { if (draft.site.kind === "application") setDraft({ ...draft, site: { ...draft.site, environments: draft.site.environments.map((old, i) => i === index ? { ...old, name: event.target.value } : old) } }); }}><option>Produkce</option><option>Vývoj</option>{!["Produkce", "Vývoj"].includes(env.name) && <option>{env.name}</option>}</select></label>
      {draft.site.kind === "application" && isMobilePlatform(draft.site.platform)
        ? <label>Bundle ID<input required data-testid={"architecture-product-bundle-" + index} placeholder="cz.example.app" value={addressValue(draft.site, env)} onChange={(event) => { if (draft.site.kind === "application") setDraft({ ...draft, site: withAddress(draft.site, index, event.target.value) }); }}/><small>Reverzní doménová notace, v projektu jedinečná. Mobilní aplikace nemá host.</small></label>
        : <label>Doména<input required data-testid={"architecture-product-host-" + index} placeholder="app.example.cz" value={draft.site.kind === "application" ? addressValue(draft.site, env) : ""} onChange={(event) => { if (draft.site.kind === "application") setDraft({ ...draft, site: withAddress(draft.site, index, event.target.value) }); }}/><small>Bez https:// a cesty. {draft.site.kind === "application" && draft.site.environments.length > 1 ? "Tyto hosty sdílejí původní stránky. Oddělení najdete na přehledu domén." : "Tato doména má vlastní stránky a vlastní ID."}</small></label>}
    </fieldset>)}
    {draft.site.kind === "page" && !!journeyRoles?.length && <div className="domain-map__form-journeys">
      <span className="domain-map__form-journeys-title">Na cestách zákazníka</span>
      <PageJourneys roles={journeyRoles} pageId={draft.id ?? "new"}/>
    </div>}
    {error && <p role="alert">{error}</p>}
    <div className="ae-row"><button type="submit" disabled={locked || !draft.name.trim()} data-testid="architecture-product-save">{saving ? "Ukládám…" : draft.id ? "Uložit změny" : "Vytvořit"}</button><button type="button" disabled={saving} onClick={onClose}>Zrušit</button></div>
  </form>;
}
