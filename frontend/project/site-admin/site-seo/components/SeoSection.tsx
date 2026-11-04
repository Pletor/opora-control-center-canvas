import { useState } from "react";
import { Field, NumberField, SelectField, TextArea, TextField, Toggle } from "@/project/site-admin/site-fields/components/Fields";
import { DESCRIPTION_SHOWN, hostProblem, readSeo, robotsContent, structuredDataProblem, structuredDataSample, templateProblem, type Seo } from "../logic/seo";
import SeoPreview from "./SeoPreview";
import "../styles/site-seo.css";

const OG_TYPES = [{ value: "website", label: "website (web)" }, { value: "article", label: "article (článek)" }, { value: "product", label: "product (produkt)" }, { value: "profile", label: "profile (osoba)" }];
const CARDS = [{ value: "summary_large_image", label: "Velký obrázek" }, { value: "summary", label: "Malý náhled" }];
const PREVIEW = [{ value: "large", label: "large (velký)" }, { value: "standard", label: "standard" }, { value: "none", label: "none (bez obrázku)" }];

/** SEO webu: titulek a popis, indexování (robots, canonical, sitemap), sdílení (Open Graph, Twitter) a JSON-LD,
 *  vedle náhled výsledku vyhledávání a karty sdílení. Dostane `settings`, celé nové SEO hlásí nahoru. */
export default function SeoSection({ settings, project, assets, onChange }: {
  settings: Record<string, unknown>; project: string; assets: string[]; onChange: (seo: Seo) => void;
}) {
  const seo = readSeo(settings);
  const [page, setPage] = useState({ title: "Úvodní stránka", path: "/" });
  const set = (patch: Partial<Seo>) => onChange({ ...seo, ...patch });
  const robots = (patch: Partial<Seo["robots"]>) => set({ robots: { ...seo.robots, ...patch } });
  const ogAsset = assets.includes(seo.ogImage);
  const jsonProblem = structuredDataProblem(seo.structuredData);
  const length = seo.description.length;
  return <div className="site-fields__split site-seo">
    <div className="site-fields__form">
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Titulek a popis</legend>
        <div className="site-fields__grid">
          <TextField label="Šablona titulku" value={seo.titleTemplate} placeholder="%s · Název webu" mono hint={templateProblem(seo.titleTemplate) || "%s nahradí titulek stránky"} onChange={(titleTemplate) => set({ titleTemplate })}/>
          <TextField label="Název webu" value={seo.siteName} placeholder="Ember" maxLength={120} hint="og:site_name a JSON-LD" onChange={(siteName) => set({ siteName })}/>
          <TextField label="Jazyk" value={seo.locale} placeholder="cs_CZ" mono maxLength={6} hint="<html lang> a og:locale" onChange={(locale) => set({ locale })}/>
          <TextArea label={`Výchozí popis (${length} / ${DESCRIPTION_SHOWN})`} value={seo.description} maxLength={500} rows={3}
            placeholder="Jedna až dvě věty o tom, co web nabízí. Stránka smí mít vlastní."
            hint={length > DESCRIPTION_SHOWN ? `Vyhledávač ukáže zhruba ${DESCRIPTION_SHOWN} znaků, zbytek ořízne.` : "Meta description; vyhledávač ho může nahradit textem stránky."} onChange={(description) => set({ description })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Indexování</legend>
        <div className="site-fields__grid">
          <Toggle label="Indexovat web (index)" checked={seo.robots.index} hint="Vypni jen na vývojové doméně." onChange={(index) => robots({ index })}/>
          <Toggle label="Sledovat odkazy (follow)" checked={seo.robots.follow} onChange={(follow) => robots({ follow })}/>
          <Toggle label="Bez archivu (noarchive)" checked={seo.robots.noarchive} onChange={(noarchive) => robots({ noarchive })}/>
          <Toggle label="Bez úryvku (nosnippet)" checked={seo.robots.nosnippet} onChange={(nosnippet) => robots({ nosnippet })}/>
          <SelectField label="Náhled obrázku" value={seo.robots.maxImagePreview} empty={null} options={PREVIEW} onChange={(maxImagePreview) => robots({ maxImagePreview })}/>
          <NumberField label="Délka úryvku" value={seo.robots.maxSnippet} min={-1} max={10000} hint="-1 = bez omezení" onChange={(maxSnippet) => robots({ maxSnippet })}/>
          <TextField label="Kanonický host" value={seo.canonicalHost} placeholder="www.example.cz" mono maxLength={253} hint={hostProblem(seo.canonicalHost) || "<link rel=canonical> na https://host + cesta"} onChange={(canonicalHost) => set({ canonicalHost })}/>
          <Toggle label="Generovat sitemap.xml" checked={seo.sitemap} hint="a odkaz na ni v robots.txt" onChange={(sitemap) => set({ sitemap })}/>
          <p className="site-fields__note">robots: <code>{robotsContent(seo.robots)}</code></p>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Sdílení (Open Graph a Twitter)</legend>
        <div className="site-fields__grid">
          <SelectField label="Obrázek z Assets" value={ogAsset ? seo.ogImage : ""} empty={assets.length ? "Bez obrázku / URL" : "Žádný obrázek v Assets"}
            options={assets.map((value) => ({ value, label: value.replace(/^assets\//, "") }))} hint="Doporučeno 1200 × 630 px" onChange={(ogImage) => set({ ogImage })}/>
          <TextField label="nebo https URL" value={ogAsset ? "" : seo.ogImage} placeholder="https://…/og.png" mono maxLength={2000} type="url" onChange={(ogImage) => set({ ogImage })}/>
          <SelectField label="og:type" value={seo.ogType} empty={null} options={OG_TYPES} onChange={(ogType) => set({ ogType })}/>
          <SelectField label="Twitter karta" value={seo.twitterCard} empty={null} options={CARDS} onChange={(twitterCard) => set({ twitterCard })}/>
          <TextField label="Twitter / X účet" value={seo.twitterSite} placeholder="@ember" mono maxLength={16} onChange={(twitterSite) => set({ twitterSite })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Strukturovaná data (JSON-LD)</legend>
        <div className="site-fields__grid">
          <TextArea label="JSON-LD (schema.org)" value={seo.structuredData} rows={8} mono maxLength={20000}
            placeholder='{"@context": "https://schema.org", "@type": "Organization", …}' hint={jsonProblem || "Dělník ho vloží do <script type=\"application/ld+json\"> v <head>."} onChange={(structuredData) => set({ structuredData })}/>
          <Field label="Vzor">
            <button type="button" className="site-fields__add" onClick={() => set({ structuredData: structuredDataSample(seo, ogAsset ? "" : seo.ogImage) })}>Vložit WebSite + Organization</button>
          </Field>
        </div>
      </fieldset>
    </div>
    <SeoPreview seo={seo} project={project} page={page} onPage={setPage}/>
  </div>;
}
