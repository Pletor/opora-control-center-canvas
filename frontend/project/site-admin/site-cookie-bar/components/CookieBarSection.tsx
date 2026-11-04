import { NumberField, Segments, TextArea, TextField, Toggle } from "@/project/site-admin/site-fields/components/Fields";
import { urlProblem } from "@/project/site-admin/site-fields/logic/settings-part";
import { emailProblem } from "@/project/site-admin/site-email/logic/email";
import { CONSENT_ADVISED, DEFAULT_TEXT, gdprAdvice, readGdpr, type CookieBar, type Gdpr, type Position } from "../logic/cookie-bar";
import CategoriesEditor from "./CategoriesEditor";
import CookieBarPreview from "./CookieBarPreview";
import "../styles/site-cookie-bar.css";

const POSITIONS = [{ value: "bottom", label: "Dole" }, { value: "top", label: "Nahoře" }, { value: "bottom-left", label: "Vlevo dole" },
  { value: "bottom-right", label: "Vpravo dole" }, { value: "center", label: "Uprostřed" }];

/** Cookie lišta (GDPR): zapnutí, umístění, texty a tlačítka, kategorie, zásady, platnost souhlasu, znovuotevření
 *  a kontakt správce; vedle náhled s funkčními tlačítky a přepínačem kategorií. Celé nové GDPR hlásí nahoru. */
export default function CookieBarSection({ settings, project, theme, componentsCss, onChange }: {
  settings: Record<string, unknown>; project: string; theme: string; componentsCss: string; onChange: (gdpr: Gdpr) => void;
}) {
  const gdpr = readGdpr(settings);
  const bar = gdpr.cookieBar;
  const set = (patch: Partial<CookieBar>) => onChange({ ...gdpr, cookieBar: { ...bar, ...patch } });
  const contact = (patch: Partial<Gdpr["contact"]>) => onChange({ ...gdpr, contact: { ...gdpr.contact, ...patch } });
  const advice = gdprAdvice(gdpr);
  return <div className="site-fields__split site-cookie-bar">
    <div className="site-fields__form">
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Lišta</legend>
        <div className="site-fields__grid">
          <Toggle label="Cookie lišta zapnutá" checked={bar.enabled} hint="Bez ní web smí používat jen nezbytné cookies." onChange={(enabled) => set({ enabled })}/>
          <Segments label="Umístění" value={bar.position} required options={POSITIONS} onChange={(position) => set({ position: position as Position })}/>
          <TextField label="Nadpis" value={bar.title} placeholder="Cookies na tomto webu" maxLength={120} onChange={(title) => set({ title })}/>
          <TextArea label="Text" value={bar.text} rows={3} maxLength={2000} placeholder={DEFAULT_TEXT} hint="Řekni, k čemu cookies jsou a že volbu jde změnit." onChange={(text) => set({ text })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Tlačítka</legend>
        <div className="site-fields__grid">
          <TextField label="Přijmout" value={bar.acceptLabel} maxLength={40} onChange={(acceptLabel) => set({ acceptLabel })}/>
          <TextField label="Odmítnout" value={bar.rejectLabel} maxLength={40} onChange={(rejectLabel) => set({ rejectLabel })}/>
          <TextField label="Nastavení" value={bar.settingsLabel} maxLength={40} onChange={(settingsLabel) => set({ settingsLabel })}/>
          <TextField label="Uložit výběr" value={bar.saveLabel} maxLength={40} onChange={(saveLabel) => set({ saveLabel })}/>
          <p className="site-fields__note">Přijmout a Odmítnout mají vždy stejný vzhled a jsou na první vrstvě (EDPB, ÚOOÚ). Zavření lišty není souhlas.</p>
        </div>
      </fieldset>
      <CategoriesEditor bar={bar} onChange={(next) => set(next)}/>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Zásady a souhlas</legend>
        <div className="site-fields__grid">
          <TextField label="Stránka zásad cookies" value={bar.policyPageId} placeholder="zasady-cookies" mono maxLength={128} onChange={(policyPageId) => set({ policyPageId, policyUrl: policyPageId ? "" : bar.policyUrl })}/>
          <TextField label="nebo URL zásad" value={bar.policyUrl} placeholder="/zasady-cookies" mono maxLength={2000} hint={urlProblem(bar.policyUrl)} onChange={(policyUrl) => set({ policyUrl, policyPageId: policyUrl ? "" : bar.policyPageId })}/>
          <NumberField label="Platnost souhlasu (dny)" value={bar.consentDays} min={1} max={730} hint={bar.consentDays > CONSENT_ADVISED ? "Víc než 13 měsíců: úřady doporučují ptát se dřív." : "Pak se web zeptá znovu."} onChange={(consentDays) => set({ consentDays })}/>
          <Toggle label="Plovoucí tlačítko „Cookies“" checked={bar.reopen} hint="Souhlas jde kdykoli změnit nebo odvolat." onChange={(reopen) => set({ reopen })}/>
          <div className="site-fields__field">
            <span className="site-fields__label">Verze lišty: {bar.version}</span>
            <button type="button" className="site-fields__add" disabled={bar.version >= 9999} onClick={() => set({ version: bar.version + 1 })}>Zeptat se všech znovu (verze {bar.version + 1})</button>
          </div>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Kontakt správce</legend>
        <div className="site-fields__grid">
          <TextField label="Správce (firma nebo jméno)" value={gdpr.contact.controller} placeholder="Ember s.r.o., IČO 12345678" maxLength={200} onChange={(controller) => contact({ controller })}/>
          <TextField label="E-mail pro GDPR" value={gdpr.contact.email} placeholder="gdpr@example.cz" type="email" maxLength={320} hint={emailProblem(gdpr.contact.email)} onChange={(email) => contact({ email: email.trim() })}/>
          <TextField label="Pověřenec (DPO), je-li" value={gdpr.contact.dpoEmail} placeholder="dpo@example.cz" type="email" maxLength={320} hint={emailProblem(gdpr.contact.dpoEmail)} onChange={(dpoEmail) => contact({ dpoEmail: dpoEmail.trim() })}/>
          <TextField label="Adresa" value={gdpr.contact.address} placeholder="Hlavní 1, 110 00 Praha" maxLength={300} onChange={(address) => contact({ address })}/>
        </div>
      </fieldset>
    </div>
    <aside className="site-fields__aside" aria-label="Náhled cookie lišty">
      <CookieBarPreview bar={bar} project={project} theme={theme} componentsCss={componentsCss}/>
      {advice.length > 0 && <ul className="site-cookie-bar__advice" role="status">{advice.map((item) => <li key={item}>{item}</li>)}</ul>}
    </aside>
  </div>;
}
