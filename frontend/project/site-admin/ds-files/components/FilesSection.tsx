import type { SiteFile } from "@/project/site-admin/logic/site-admin-api";
import "../styles/ds-files.css";

const FILES: { name: SiteFile; what: string }[] = [
  { name: "tokens.css", what: "Proměnné všech témat, třídy typografických stylů a @font-face. Web ho načte jako první stylesheet." },
  { name: "tokens.json", what: "Tokeny v gramatice formátu Design System pro nástroje a kontrolu." },
  { name: "README.md", what: "Brand book a generovaná část „Jak systém použít“. Dělník ho čte jako první." },
];

/** Files: odvozené soubory systému ke stažení. Generuje je server z uložené revize; rozepsané změny v nich nejsou,
 *  proto dílek řekne, ze které revize soubory jsou. Adresy dostane hotové od rodiče. */
export default function FilesSection({ revision, dirty, urls }: { revision: number; dirty: boolean; urls: Record<SiteFile, string> }) {
  return <div className="ds-files">
    <p className="ds-files__lead">Soubory generuje server z uložené revize <b>{revision}</b>{dirty ? " — neuložené změny v nich zatím nejsou, nejdřív ulož." : "."}</p>
    <ul className="ds-files__list">
      {FILES.map((file) => <li key={file.name} className="ds-files__item">
        <span className="ds-files__icon" aria-hidden="true">{file.name.endsWith(".css") ? "#" : file.name.endsWith(".json") ? "{}" : "¶"}</span>
        <div className="ds-files__text"><code className="ds-files__name">design/{file.name}</code><small className="ds-files__what">{file.what}</small></div>
        <a className="ds-files__open" href={urls[file.name]} target="_blank" rel="noreferrer">Otevřít</a>
        <a className="ds-files__download" href={urls[file.name]} download={file.name} data-testid={"site-file-" + file.name}>Stáhnout</a>
      </li>)}
    </ul>
  </div>;
}
