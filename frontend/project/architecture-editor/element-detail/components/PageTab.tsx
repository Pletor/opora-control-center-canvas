import { useRef, useState } from "react";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import type { CanvasNode, PageSite } from "@/shared/types/logic/types";
import { PAGE_INTENT_FIELDS, withPageIntent } from "../../domain-map/logic/page-site";
import { pageJourneyText, type PageJourneyRole } from "../../domain-map/logic/page-journeys";
import PageSectionsEditor from "../../page-sections/components/PageSectionsEditor";

type Props = {
  /** Vybraná stránka (`site.kind = "page"`). */
  page: CanvasNode & { site: PageSite };
  /** Kroky cest aplikace, které vedou na tuto stránku (`journeysOfPage`); jen ke čtení. */
  roles: PageJourneyRole[];
  disabled: boolean;
  /** Uloží záměr a sekce; `original` je stránka, ze které koncept vznikl. Chyba zůstane u formuláře. */
  onSave: (original: CanvasNode, site: PageSite) => Promise<void>;
};

/**
 * Záložka Stránka v Detailu prvku: k jakému posunu stránka slouží (z cest, jen ke čtení), cíl, působení,
 * popisek v menu a rozbor sekcí s „Čím posouvá“ přes sdílený `PageSectionsEditor`. Koncept je lokální:
 * první změna si zapamatuje stránku, ze které vznikl, a uloží se až tlačítkem. Rodič dává `key` podle id.
 */
export default function PageTab({ page, roles, disabled, onSave }: Props) {
  const [draft, setDraft] = useState<{ base: CanvasNode; site: PageSite } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const site = draft?.site ?? page.site;
  const dirty = draft !== null;
  const locked = disabled || saving;
  const changed = useRef(dirty); changed.current = dirty;
  const edit = (next: PageSite) => setDraft((current) => ({ base: current?.base ?? page, site: next }));
  useScopedSaveParticipant({ id: `architecture-page:${page.id}`, label: `Stránka: ${page.name}`,
    dirty, pending: saving, isDirty: () => changed.current,
    blocked: disabled ? "Stránku nyní nelze upravovat." : undefined,
    flush: () => confirmSavedChange(() => draft ? onSave(draft.base, draft.site) : Promise.resolve(), () => changed.current) });

  async function save() {
    if (!draft || locked) return;
    setSaving(true);
    setError("");
    try {
      await onSave(draft.base, draft.site);
      setDraft(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="element-detail__form" data-testid="element-detail-page" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      {roles.length ? (
        <ul className="element-detail__journeys" aria-label="Na cestě zákazníka">
          {roles.map((role) => <li key={role.journeyId + ":" + role.stepId} className="element-detail__journey">{pageJourneyText(role)}</li>)}
        </ul>
      ) : <p className="element-detail__muted">Stránka není na žádné cestě zákazníka.</p>}
      {PAGE_INTENT_FIELDS.map(({ key, label, max, placeholder }) => (
        <label key={key} className="element-detail__field">
          <span className="element-detail__field-label">{label}</span>
          <input className="element-detail__input" maxLength={max} placeholder={placeholder} disabled={locked} data-testid={"element-detail-page-" + key}
            value={site[key] ?? ""} onChange={(event) => edit(withPageIntent(site, key, event.target.value))} />
        </label>
      ))}
      <PageSectionsEditor site={site} disabled={locked} onChange={edit} />
      {error ? <p className="element-detail__error" role="alert">{error}</p> : null}
      <div className="element-detail__actions">
        {dirty ? <span className="element-detail__hint">Neuložený koncept</span> : null}
        <button type="button" className="element-detail__button" disabled={!dirty || locked} onClick={() => { setDraft(null); setError(""); }}>Zahodit</button>
        <button type="submit" className="element-detail__button element-detail__button--primary" disabled={!dirty || locked}>{saving ? "Ukládám…" : "Uložit"}</button>
      </div>
    </form>
  );
}
