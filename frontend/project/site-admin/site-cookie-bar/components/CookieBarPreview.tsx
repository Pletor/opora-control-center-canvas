import { useState } from "react";
import WebStage from "@/project/site-admin/ds-preview/components/WebStage";
import { linkHref } from "@/project/site-admin/site-fields/logic/settings-part";
import { acceptAll, barClass, DEFAULT_TEXT, info, initialConsent, toggleConsent, type Consent, type CookieBar } from "../logic/cookie-bar";

const stop = (event: { preventDefault: () => void }) => event.preventDefault();

/** Výřez webu s cookie lištou tak, jak ji uvidí návštěvník, v tokenech a `components.css` projektu. Tlačítka
 *  fungují: Nastavení ukáže přepínače kategorií (předem vypnuté), Přijmout / Odmítnout / Uložit lištu zavřou
 *  a plovoucí tlačítko ji otevře znovu. Nic se neukládá, je to jen zkouška chování. */
export default function CookieBarPreview({ bar, project, theme, componentsCss }: { bar: CookieBar; project: string; theme: string; componentsCss: string }) {
  const [consent, setConsent] = useState<Consent>(initialConsent);
  const [open, setOpen] = useState(true);
  const [detail, setDetail] = useState(false);
  const [saved, setSaved] = useState<Consent | null>(null);
  const decide = (choice: Consent) => { setConsent(choice); setSaved(choice); setOpen(false); setDetail(false); };
  const policy = bar.policyPageId || bar.policyUrl ? linkHref({ pageId: bar.policyPageId, url: bar.policyUrl }) : "";
  const chosen = saved ? bar.categories.filter((item) => saved[item]).map((item) => info(bar, item).label).join(", ") : "";
  return <div className="site-cookie-bar__preview" data-testid="cookie-bar-preview">
    <WebStage project={project} theme={theme} componentsCss={componentsCss} name="cookie-bar" className="site-cookie-bar__stage">
      <div className="ds-container site-cookie-bar__page">
        <h2>Stránka webu</h2>
        <p>{bar.enabled ? "Tady návštěvník čte obsah a dole se mu ukáže cookie lišta." : "Lišta je vypnutá: web smí používat jen nezbytné cookies."}</p>
        {saved && <p className="site-cookie-bar__result" role="status">Uložená volba: {chosen || "jen nezbytné"} (platí {bar.consentDays} dní).</p>}
      </div>
      {bar.enabled && open && <section className={barClass(bar)} role="dialog" aria-modal="false" aria-labelledby="cookie-preview-title">
        <h2 className="ds-cookie-bar__title" id="cookie-preview-title">{bar.title || "Cookies na tomto webu"}</h2>
        <p className="ds-cookie-bar__text">{bar.text || DEFAULT_TEXT}{policy && <> <a className="ds-cookie-bar__policy" href={policy} onClick={stop}>Zásady cookies</a></>}</p>
        {detail && <fieldset className="ds-cookie-bar__categories">
          {bar.categories.map((item) => <label key={item} className="ds-cookie-bar__category">
            <input type="checkbox" checked={consent[item]} disabled={item === "necessary"} onChange={() => setConsent(toggleConsent(consent, item))}/>
            <span>{info(bar, item).label}</span>
            <small className="ds-cookie-bar__category-note">{info(bar, item).description}</small>
          </label>)}
        </fieldset>}
        <div className="ds-cookie-bar__actions">
          <button type="button" className="ds-cookie-bar__choice" onClick={() => decide(acceptAll(bar))}>{bar.acceptLabel}</button>
          <button type="button" className="ds-cookie-bar__choice" onClick={() => decide(initialConsent())}>{bar.rejectLabel}</button>
          {detail
            ? <button type="button" className="ds-cookie-bar__choice ds-cookie-bar__choice--settings" onClick={() => decide(consent)}>{bar.saveLabel}</button>
            : <button type="button" className="ds-cookie-bar__choice ds-cookie-bar__choice--settings" aria-expanded={false} onClick={() => setDetail(true)}>{bar.settingsLabel}</button>}
        </div>
      </section>}
      {bar.enabled && !open && bar.reopen && <button type="button" className="ds-cookie-reopen" onClick={() => setOpen(true)}>Cookies</button>}
    </WebStage>
    <div className="site-cookie-bar__tools">
      <button type="button" className="site-fields__add" onClick={() => { setOpen(true); setDetail(false); setSaved(null); setConsent(initialConsent()); }}>Ukázat jako nový návštěvník</button>
      <button type="button" className="site-fields__add" onClick={() => { setOpen(true); setDetail(true); }}>Otevřít přepínač kategorií</button>
    </div>
  </div>;
}
