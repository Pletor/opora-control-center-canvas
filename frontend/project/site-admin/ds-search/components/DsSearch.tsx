import { useState } from "react";
import type { Design } from "@/project/site-admin/logic/site-document";
import { searchDesign, type SearchHit } from "../logic/search";
import "../styles/ds-search.css";

/** Search nad menu (`image9.png`): hledá v rozepsaném design systému a výsledek hlásí `onPick`; rodič přepne sekci
 *  a zvýrazní položku. Escape pole vyčistí. */
export default function DsSearch({ design, onPick }: { design: Design; onPick: (hit: SearchHit) => void }) {
  const [query, setQuery] = useState("");
  const hits = searchDesign(design, query);
  return <div className="ds-search" role="search">
    <input className="ds-search__input" type="search" placeholder="Search" aria-label="Hledat v design systému" value={query}
      onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") setQuery(""); }}/>
    {query.trim() && <ul className="ds-search__results" aria-label="Výsledky hledání">
      {hits.length ? hits.map((hit) => <li key={hit.target}>
        <button type="button" className="ds-search__hit-button" onClick={() => onPick(hit)}>
          <span className="ds-search__kind">{hit.kind}</span>
          <b className="ds-search__label">{hit.label}</b>
          {hit.detail && <small className="ds-search__detail">{hit.detail}</small>}
        </button>
      </li>) : <li className="ds-search__none">Nic nenalezeno.</li>}
    </ul>}
  </div>;
}
