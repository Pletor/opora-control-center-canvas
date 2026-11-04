import { Segments, TextArea, Toggle } from "@/project/site-admin/site-fields/components/Fields";
import LinkListEditor from "@/project/site-admin/site-fields/components/LinkListEditor";
import { moveAt, removeAt, replaceAt } from "@/project/site-admin/site-fields/logic/settings-part";
import { footerAdvice, MAX_COLUMNS, MAX_LINKS, MAX_SOCIAL, NETWORKS, readFooter, socialProblem, type Footer, type FooterVariant } from "../logic/footer";
import FooterPreview from "./FooterPreview";
import "../styles/site-footer.css";

const VARIANTS = [{ value: "columns", label: "Sloupce" }, { value: "simple", label: "Jeden řádek" }, { value: "centered", label: "Na střed" }];

/** Patička webu: rozvržení, sloupce odkazů, sociální sítě, právní řádek a odkaz na nastavení cookies, nad tím
 *  živý náhled. Celou novou patičku hlásí nahoru. */
export default function FooterSection({ settings, project, theme, componentsCss, onChange }: {
  settings: Record<string, unknown>; project: string; theme: string; componentsCss: string; onChange: (footer: Footer) => void;
}) {
  const footer = readFooter(settings);
  const set = (patch: Partial<Footer>) => onChange({ ...footer, ...patch });
  const advice = footerAdvice(footer);
  return <div className="site-footer">
    <FooterPreview footer={footer} project={project} theme={theme} componentsCss={componentsCss}/>
    <div className="site-fields__form">
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Rozvržení a právní řádek</legend>
        <div className="site-fields__grid">
          <Segments label="Rozvržení" value={footer.variant} required options={VARIANTS} onChange={(variant) => set({ variant: variant as FooterVariant })}/>
          <Toggle label="Odkaz „Nastavení cookies“" checked={footer.cookieLink} hint="Návštěvník tudy kdykoli změní nebo odvolá souhlas." onChange={(cookieLink) => set({ cookieLink })}/>
          <TextArea label="Právní řádek" value={footer.legal} rows={2} maxLength={2000} placeholder="© {rok} Ember s.r.o., IČO 12345678, Hlavní 1, Praha"
            hint={advice || "{rok} se nahradí letošním rokem."} onChange={(legal) => set({ legal })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Sloupce odkazů ({footer.columns.length} / {MAX_COLUMNS})</legend>
        <div className="site-footer__columns">
          {footer.columns.map((column, index) => <div key={index} className="site-footer__column">
            <div className="site-footer__column-head">
              <input className="site-fields__input" value={column.title} placeholder="Nadpis sloupce" aria-label={`Sloupec ${index + 1}: nadpis`} maxLength={80}
                onChange={(event) => set({ columns: replaceAt(footer.columns, index, { ...column, title: event.target.value }) })}/>
              <button type="button" className="site-fields__icon" aria-label={`Sloupec ${index + 1} doleva`} disabled={index === 0} onClick={() => set({ columns: moveAt(footer.columns, index, -1) })}>←</button>
              <button type="button" className="site-fields__icon" aria-label={`Sloupec ${index + 1} doprava`} disabled={index === footer.columns.length - 1} onClick={() => set({ columns: moveAt(footer.columns, index, 1) })}>→</button>
              <button type="button" className="site-fields__icon" aria-label={`Odebrat sloupec ${column.title || index + 1}`} onClick={() => set({ columns: removeAt(footer.columns, index) })}>×</button>
            </div>
            <LinkListEditor label={`Odkaz sloupce ${column.title || index + 1}`} links={column.links} limit={MAX_LINKS}
              onChange={(links) => set({ columns: replaceAt(footer.columns, index, { ...column, links }) })}/>
          </div>)}
          <button type="button" className="site-fields__add" disabled={footer.columns.length >= MAX_COLUMNS} onClick={() => set({ columns: [...footer.columns, { title: "", links: [] }] })}>+ Sloupec</button>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Sociální sítě ({footer.social.length} / {MAX_SOCIAL})</legend>
        <div className="site-footer__social">
          {footer.social.map((item, index) => {
            const problem = socialProblem(item);
            return <div key={index} className="site-footer__social-row">
              <select className="site-fields__input" value={item.name} aria-label={`Síť ${index + 1}`} onChange={(event) => set({ social: replaceAt(footer.social, index, { ...item, name: event.target.value }) })}>
                {Object.entries(NETWORKS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <input className="site-fields__input site-fields__input--mono" value={item.url} placeholder="https://instagram.com/…" aria-label={`Síť ${index + 1}: adresa`} maxLength={2000}
                onChange={(event) => set({ social: replaceAt(footer.social, index, { ...item, url: event.target.value }) })}/>
              <button type="button" className="site-fields__icon" aria-label={`Odebrat síť ${index + 1}`} onClick={() => set({ social: removeAt(footer.social, index) })}>×</button>
              {problem && <small className="site-fields__problem" role="alert">{problem}</small>}
            </div>;
          })}
          <button type="button" className="site-fields__add" disabled={footer.social.length >= MAX_SOCIAL} onClick={() => set({ social: [...footer.social, { name: "instagram", url: "" }] })}>+ Síť</button>
        </div>
      </fieldset>
    </div>
  </div>;
}
