import { EMPTY_LINK, linkProblem, moveAt, removeAt, replaceAt, type SiteLink } from "../logic/settings-part";

/** Seznam odkazů (menu hlavičky, sloupec patičky): popisek, cíl stránka nebo URL, pořadí šipkami a odebrání.
 *  Chyba řádku se ukáže hned pod ním, stejnými slovy jako server. Celý nový seznam hlásí nahoru. */
export default function LinkListEditor({ label, links, limit, onChange }: {
  label: string; links: SiteLink[]; limit: number; onChange: (links: SiteLink[]) => void;
}) {
  const set = (index: number, link: SiteLink) => onChange(replaceAt(links, index, link));
  return <div className="site-fields__links" role="group" aria-label={label}>
    {links.map((link, index) => {
      const page = !link.url;  // shortcut: smazaná URL přepne řádek na stránku; stačí, dokud se cíl píše ručně
      const problem = linkProblem(link);
      return <div key={index} className="site-fields__link-row">
        <input className="site-fields__input" value={link.label} placeholder="Popisek" aria-label={`${label} ${index + 1}: popisek`} maxLength={80}
          onChange={(event) => set(index, { ...link, label: event.target.value })}/>
        <select className="site-fields__input" value={page ? "page" : "url"} aria-label={`${label} ${index + 1}: cíl`}
          onChange={(event) => set(index, event.target.value === "page" ? { ...link, url: "" } : { ...link, pageId: "", url: "/" })}>
          <option value="page">Stránka</option><option value="url">URL</option>
        </select>
        <input className="site-fields__input site-fields__input--mono" value={page ? link.pageId : link.url} placeholder={page ? "id stránky (kontakt)" : "/cesta nebo https://…"}
          aria-label={`${label} ${index + 1}: ${page ? "stránka" : "URL"}`} maxLength={page ? 128 : 2000} spellCheck={false}
          onChange={(event) => set(index, page ? { ...link, pageId: event.target.value, url: "" } : { ...link, url: event.target.value, pageId: "" })}/>
        <span className="site-fields__row-tools">
          <button type="button" className="site-fields__icon" aria-label={`Posunout ${link.label || index + 1} nahoru`} disabled={index === 0} onClick={() => onChange(moveAt(links, index, -1))}>↑</button>
          <button type="button" className="site-fields__icon" aria-label={`Posunout ${link.label || index + 1} dolů`} disabled={index === links.length - 1} onClick={() => onChange(moveAt(links, index, 1))}>↓</button>
          <button type="button" className="site-fields__icon" aria-label={`Odebrat ${link.label || index + 1}`} onClick={() => onChange(removeAt(links, index))}>×</button>
        </span>
        {problem && <small className="site-fields__problem" role="alert">{problem}</small>}
      </div>;
    })}
    <button type="button" className="site-fields__add" disabled={links.length >= limit} onClick={() => onChange([...links, { ...EMPTY_LINK }])}>
      + Odkaz {links.length >= limit ? `(nejvýš ${limit})` : ""}
    </button>
  </div>;
}
