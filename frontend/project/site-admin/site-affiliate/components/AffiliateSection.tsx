import { useState } from "react";
import { NumberField, Segments, TextArea, TextField, Toggle } from "@/project/site-admin/site-fields/components/Fields";
import { removeAt, replaceAt } from "@/project/site-admin/site-fields/logic/settings-part";
import { attributionText, EMPTY_PROGRAM, MAX_PROGRAMS, paramProblem, partnerLink, programProblem, readAffiliate, type Affiliate } from "../logic/affiliate";
import "../styles/site-affiliate.css";

/** Affiliate webu: zapnutí, parametr odkazu, platnost cookie, atribuce, upozornění pro návštěvníky a provizní
 *  programy; vedle ukázkový odkaz partnera a věta, kdo dostane provizi. Celý nový Affiliate hlásí nahoru. */
export default function AffiliateSection({ settings, host, marketing, onChange }: {
  settings: Record<string, unknown>; host: string; marketing: boolean; onChange: (affiliate: Affiliate) => void;
}) {
  const affiliate = readAffiliate(settings);
  const [code, setCode] = useState("PARTNER");
  const set = (patch: Partial<Affiliate>) => onChange({ ...affiliate, ...patch });
  return <div className="site-fields__split site-affiliate">
    <div className="site-fields__form">
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Partnerský program</legend>
        <div className="site-fields__grid">
          <Toggle label="Affiliate zapnutý" checked={affiliate.enabled} hint="Web si zapamatuje kód partnera z odkazu." onChange={(enabled) => set({ enabled })}/>
          <TextField label="Parametr v odkazu" value={affiliate.param} mono maxLength={32} hint={paramProblem(affiliate.param) || `?${affiliate.param}=KOD`} onChange={(param) => set({ param: param.toLowerCase() })}/>
          <NumberField label="Platnost cookie (dny)" value={affiliate.cookieDays} min={1} max={365} onChange={(cookieDays) => set({ cookieDays })}/>
          <Segments label="Atribuce" value={affiliate.attribution} required options={[{ value: "last", label: "Poslední klik" }, { value: "first", label: "První klik" }]} onChange={(attribution) => set({ attribution })}/>
          <TextArea label="Upozornění u provizních odkazů" value={affiliate.disclosure} maxLength={500} rows={2}
            placeholder="Některé odkazy jsou partnerské. Když přes ně nakoupíš, dostaneme provizi; cena se pro tebe nemění."
            hint="Návštěvník musí vědět, že odkaz je placený (ochrana spotřebitele)." onChange={(disclosure) => set({ disclosure })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Programy ({affiliate.programs.length} / {MAX_PROGRAMS})</legend>
        <div className="site-affiliate__programs">
          {affiliate.programs.map((program, index) => {
            const edit = (patch: Partial<typeof program>) => set({ programs: replaceAt(affiliate.programs, index, { ...program, ...patch }) });
            const problem = programProblem(program);
            return <div key={index} className="site-affiliate__program">
              <input className="site-fields__input" value={program.name} placeholder="Jméno (Heureka)" aria-label={`Program ${index + 1}: jméno`} maxLength={120} onChange={(event) => edit({ name: event.target.value })}/>
              <input className="site-fields__input site-fields__input--mono" value={program.url} placeholder="https://…" aria-label={`Program ${index + 1}: adresa`} maxLength={2000} onChange={(event) => edit({ url: event.target.value })}/>
              <input className="site-fields__input" value={program.commission} placeholder="Provize (5 %)" aria-label={`Program ${index + 1}: provize`} maxLength={100} onChange={(event) => edit({ commission: event.target.value })}/>
              <input className="site-fields__input site-fields__input--mono" value={program.code} placeholder="Kód" aria-label={`Program ${index + 1}: kód`} maxLength={64} onChange={(event) => edit({ code: event.target.value })}/>
              <button type="button" className="site-fields__icon" aria-label={`Odebrat program ${program.name || index + 1}`} onClick={() => set({ programs: removeAt(affiliate.programs, index) })}>×</button>
              {problem && <small className="site-fields__problem" role="alert">{problem}</small>}
            </div>;
          })}
          <button type="button" className="site-fields__add" disabled={affiliate.programs.length >= MAX_PROGRAMS} onClick={() => set({ programs: [...affiliate.programs, { ...EMPTY_PROGRAM }] })}>+ Program</button>
        </div>
      </fieldset>
    </div>
    <aside className="site-fields__aside site-affiliate__preview" aria-label="Náhled affiliate" data-testid="affiliate-preview">
      <h3 className="site-affiliate__heading">Odkaz partnera</h3>
      <input className="site-fields__input site-fields__input--mono" value={code} aria-label="Kód partnera v ukázce" maxLength={32} onChange={(event) => setCode(event.target.value)}/>
      <code className="site-affiliate__link">{partnerLink(host, affiliate.param, code)}</code>
      <p className="site-affiliate__text">{attributionText(affiliate)}</p>
      {affiliate.enabled && !marketing && <p className="site-affiliate__warn" role="status">Cookie lišta nemá kategorii Marketing: kód partnera se bez ní nesmí uložit. Zapni ji v GDPR → Cookie lišta.</p>}
      {affiliate.disclosure && <p className="site-affiliate__disclosure">{affiliate.disclosure}</p>}
    </aside>
  </div>;
}
