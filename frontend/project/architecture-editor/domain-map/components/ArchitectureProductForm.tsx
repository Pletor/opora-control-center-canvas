import { useEffect, useRef, useState } from "react";
import type { ProductDraft } from "@/project/product-tree/logic/product-tree";
import { normalizePagePath } from "@/project/product-tree/logic/page-path";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";

/** Structural identity belongs to the domain map; working specifications stay in Editor. */
export default function ArchitectureProductForm({ initial, disabled, onSave, onClose }: {
  initial: ProductDraft; disabled: boolean; onSave: (draft: ProductDraft) => Promise<void>; onClose: () => void;
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
      const site = draft.site.kind === "page" ? { ...draft.site, path: normalizePagePath(draft.site.path) } : {
        ...draft.site, environments: draft.site.environments.map((env) => ({ name: env.name.trim(), host: env.host.trim() })),
      };
      await onSave({ ...draft, site }); onClose();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  }
  return <form ref={form} className="ae-form ae-product-form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <h3>{draft.id ? "Upravit" : "Přidat"} {draft.site.kind === "page" ? "stránku" : "doménu"}</h3>
    <label>Název<input required maxLength={160} disabled={locked} data-testid="architecture-product-name" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })}/></label>
    <label>Účel<textarea rows={3} maxLength={4000} disabled={locked} data-testid="architecture-product-purpose" value={draft.purpose} onChange={(event) => setDraft({ ...draft, purpose: event.target.value })}/></label>
    {draft.site.kind === "page" ? <label>Cesta stránky<input required maxLength={2048} placeholder="/kontakt" disabled={locked} data-testid="architecture-product-path" value={draft.site.path} onChange={(event) => setDraft({ ...draft, site: { kind: "page", path: event.target.value } })}/><small>Například kontakt uložíme jako /kontakt. Použijte cestu bez domény, parametrů a #.</small></label> : draft.site.environments.map((env, index) => <fieldset key={index} disabled={locked}>
      <label>Prostředí<select value={env.name} data-testid="architecture-product-environment" onChange={(event) => { if (draft.site.kind === "application") setDraft({ ...draft, site: { ...draft.site, environments: draft.site.environments.map((old, i) => i === index ? { ...old, name: event.target.value } : old) } }); }}><option>Produkce</option><option>Vývoj</option>{!["Produkce", "Vývoj"].includes(env.name) && <option>{env.name}</option>}</select></label>
      <label>Doména<input required data-testid={"architecture-product-host-" + index} placeholder="app.example.cz" value={env.host} onChange={(event) => { if (draft.site.kind === "application") setDraft({ ...draft, site: { ...draft.site, environments: draft.site.environments.map((old, i) => i === index ? { ...old, host: event.target.value } : old) } }); }}/><small>Bez https:// a cesty. {draft.site.kind === "application" && draft.site.environments.length > 1 ? "Tyto hosty sdílejí původní stránky. Oddělení najdete na přehledu domén." : "Tato doména má vlastní stránky a vlastní ID."}</small></label>
    </fieldset>)}
    {error && <p role="alert">{error}</p>}
    <div className="ae-row"><button type="submit" disabled={locked || !draft.name.trim()} data-testid="architecture-product-save">{saving ? "Ukládám…" : draft.id ? "Uložit změny" : "Vytvořit"}</button><button type="button" disabled={saving} onClick={onClose}>Zrušit</button></div>
  </form>;
}
