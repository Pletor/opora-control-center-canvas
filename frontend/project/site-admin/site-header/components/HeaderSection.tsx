import { Segments, SelectField, TextField, Toggle } from "@/project/site-admin/site-fields/components/Fields";
import LinkListEditor from "@/project/site-admin/site-fields/components/LinkListEditor";
import { ctaProblem, MAX_ITEMS, readHeader, type Header, type HeaderVariant } from "../logic/header";
import HeaderPreview from "./HeaderPreview";
import "../styles/site-header.css";

const VARIANTS = [{ value: "classic", label: "Logo vlevo, menu vpravo" }, { value: "centered", label: "Na střed" }, { value: "minimal", label: "Kompaktní" }];

/** Hlavička webu: logo z Assets, menu ze stránek mapy domény nebo ruční, CTA tlačítko, přilepení a rozvržení;
 *  nad formulářem živý náhled nad `components.css` projektu. Celou novou hlavičku hlásí nahoru. */
export default function HeaderSection({ settings, project, theme, componentsCss, assets, variants, onChange }: {
  settings: Record<string, unknown>; project: string; theme: string; componentsCss: string; assets: string[]; variants: string[];
  onChange: (header: Header) => void;
}) {
  const header = readHeader(settings);
  const set = (patch: Partial<Header>) => onChange({ ...header, ...patch });
  const cta = (patch: Partial<Header["cta"]>) => set({ cta: { ...header.cta, ...patch } });
  const problem = ctaProblem(header);
  return <div className="site-header">
    <HeaderPreview header={header} project={project} theme={theme} componentsCss={componentsCss} variants={variants}/>
    <div className="site-fields__form">
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Logo a rozvržení</legend>
        <div className="site-fields__grid">
          <SelectField label="Logo z Assets" value={header.logoAsset} empty={assets.length ? "Bez loga (jméno webu)" : "Žádný obrázek v Assets"}
            options={assets.map((value) => ({ value, label: value.replace(/^assets\//, "") }))} onChange={(logoAsset) => set({ logoAsset })}/>
          <TextField label="Alternativní text loga" value={header.logoAlt} placeholder="Jméno webu" maxLength={120} hint="Čte ho čtečka obrazovky místo obrázku." onChange={(logoAlt) => set({ logoAlt })}/>
          <Segments label="Rozvržení" value={header.variant} required options={VARIANTS} onChange={(variant) => set({ variant: variant as HeaderVariant })}/>
          <Toggle label="Přilepit nahoru (sticky)" checked={header.sticky} hint="Hlavička zůstane vidět při posouvání stránky." onChange={(sticky) => set({ sticky })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Menu</legend>
        <div className="site-fields__grid">
          <Segments label="Zdroj menu" value={header.nav} required options={[{ value: "source:pages", label: "Hlavní stránky z mapy domény" }, { value: "manual", label: "Ruční menu" }]}
            onChange={(nav) => set({ nav: nav as Header["nav"] })}/>
          <p className="site-fields__note">{header.nav === "source:pages"
            ? "Menu skládá dělník z hlavních stránek mapy domény v jejich pořadí. Odkazy níže se přidají za ně (blog, e-shop)."
            : "Menu je přesně tenhle seznam v tomhle pořadí."}</p>
          <LinkListEditor label={header.nav === "manual" ? "Položka menu" : "Odkaz navíc"} links={header.items} limit={MAX_ITEMS} onChange={(items) => set({ items })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Tlačítko výzvy (CTA)</legend>
        <div className="site-fields__grid">
          <TextField label="Text tlačítka" value={header.cta.label} placeholder="Rezervovat" maxLength={40} hint="Prázdné = bez tlačítka." onChange={(label) => cta({ label })}/>
          <TextField label="Stránka" value={header.cta.pageId} placeholder="rezervace" mono maxLength={128} onChange={(pageId) => cta({ pageId, url: pageId ? "" : header.cta.url })}/>
          <TextField label="nebo URL" value={header.cta.url} placeholder="https://…" mono maxLength={2000} onChange={(url) => cta({ url, pageId: url ? "" : header.cta.pageId })}/>
          <SelectField label="Varianta tlačítka" value={header.cta.variant} empty={variants.length ? `Výchozí (${variants[0]})` : "Nejdřív přidej Tlačítka webu"}
            options={variants.map((value) => ({ value, label: value }))} onChange={(variant) => cta({ variant })}/>
          {problem && <small className="site-fields__problem" role="alert">{problem}</small>}
        </div>
      </fieldset>
    </div>
  </div>;
}
