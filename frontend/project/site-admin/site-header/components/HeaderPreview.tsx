import WebStage from "@/project/site-admin/ds-preview/components/WebStage";
import { imageSrc, linkHref } from "@/project/site-admin/site-fields/logic/settings-part";
import { ctaView, headerClass, navItems, type Header } from "../logic/header";

const stop = (event: { preventDefault: () => void }) => event.preventDefault();

/** Výřez webu s hlavičkou a kusem stránky pod ní, v tokenech a `components.css` projektu. Přilepená hlavička
 *  zůstane nahoře, když se výřez posune. Odkazy nikam nevedou. */
export default function HeaderPreview({ header, project, theme, componentsCss, variants }: {
  header: Header; project: string; theme: string; componentsCss: string; variants: string[];
}) {
  const logo = imageSrc(project, header.logoAsset);
  const cta = ctaView(header, variants);
  const items = navItems(header);
  return <div className="site-header__preview" aria-label="Náhled hlavičky" data-testid="header-preview">
    <WebStage project={project} theme={theme} componentsCss={componentsCss} name="header" className="site-header__stage">
      <header className={headerClass(header)}>
        <div className="ds-header__inner">
          <a className="ds-header__logo" href="/" onClick={stop}>
            {logo ? <img className="ds-header__logo-img" src={logo} alt={header.logoAlt}/> : header.logoAlt || "Logo webu"}
          </a>
          <nav className="ds-header__nav" aria-label="Hlavní menu (náhled)">
            {items.map((item, index) => <a key={index} className="ds-header__link" href={linkHref(item)} aria-current={index === 0 ? "page" : undefined} onClick={stop}>{item.label}</a>)}
          </nav>
          {cta.show && <a className={cta.className} href={cta.href} onClick={stop}>{header.cta.label}</a>}
        </div>
      </header>
      <div className="ds-container site-header__page">
        <h1>Nadpis stránky</h1>
        <p>Obsah stránky pod hlavičkou. Posuň výřez a uvidíš, jestli hlavička zůstane nahoře.</p>
        <p>Další odstavec, aby bylo co posouvat.</p>
      </div>
    </WebStage>
  </div>;
}
