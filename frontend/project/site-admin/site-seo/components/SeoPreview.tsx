import { imageSrc } from "@/project/site-admin/site-fields/logic/settings-part";
import { clip, DESCRIPTION_SHOWN, pageTitle, searchCrumb, TITLE_SHOWN, type Seo } from "../logic/seo";

type Page = { title: string; path: string };

/** Jak web uvidí vyhledávač a sociální síť: výsledek vyhledávání (titulek podle šablony, adresa, popis oříznutý
 *  jako ve výsledcích) a karta sdílení s obrázkem. Titulek a cestu ukázkové stránky jde přepsat. */
export default function SeoPreview({ seo, project, page, onPage }: { seo: Seo; project: string; page: Page; onPage: (page: Page) => void }) {
  const title = pageTitle(seo.titleTemplate, page.title);
  const host = seo.canonicalHost || "www.example.cz";
  const image = imageSrc(project, seo.ogImage);
  const description = seo.description || "Popis zatím chybí, vyhledávač si vezme text ze stránky.";
  return <aside className="site-fields__aside site-seo__preview" aria-label="Náhled SEO" data-testid="seo-preview">
    <div className="site-seo__page">
      <input className="site-fields__input" value={page.title} aria-label="Titulek ukázkové stránky" maxLength={80} onChange={(event) => onPage({ ...page, title: event.target.value })}/>
      <input className="site-fields__input site-fields__input--mono" value={page.path} aria-label="Cesta ukázkové stránky" maxLength={120} onChange={(event) => onPage({ ...page, path: event.target.value })}/>
    </div>
    <h3 className="site-seo__heading">Výsledek vyhledávání</h3>
    <div className={"site-seo__serp" + (seo.robots.index ? "" : " site-seo__serp--hidden")}>
      <span className="site-seo__site"><span className="site-seo__favicon" aria-hidden="true">{(seo.siteName || host).charAt(0).toUpperCase()}</span>
        <span><b className="site-seo__site-name">{seo.siteName || host}</b><small className="site-seo__crumb">{searchCrumb(host, page.path)}</small></span></span>
      <span className="site-seo__title">{clip(title, TITLE_SHOWN)}</span>
      {!seo.robots.nosnippet && <span className="site-seo__snippet">{clip(description, seo.robots.maxSnippet >= 0 ? Math.min(seo.robots.maxSnippet, DESCRIPTION_SHOWN) : DESCRIPTION_SHOWN)}</span>}
      {!seo.robots.index && <span className="site-seo__badge" role="status">noindex: tahle stránka se ve výsledcích neukáže</span>}
    </div>
    <h3 className="site-seo__heading">Sdílení ({seo.twitterCard === "summary" ? "malý náhled" : "velký obrázek"})</h3>
    <div className={"site-seo__card site-seo__card--" + (seo.twitterCard === "summary" ? "small" : "large")}>
      <span className="site-seo__card-image">{image ? <img className="site-seo__card-img" src={image} alt=""/> : <span className="site-seo__card-empty">Bez obrázku og:image</span>}</span>
      <span className="site-seo__card-body">
        <small className="site-seo__card-host">{host.toUpperCase()}</small>
        <b className="site-seo__card-title">{title}</b>
        <span className="site-seo__card-text">{clip(description, 110)}</span>
      </span>
    </div>
  </aside>;
}
