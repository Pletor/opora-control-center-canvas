import WebStage from "@/project/site-admin/ds-preview/components/WebStage";
import { linkHref } from "@/project/site-admin/site-fields/logic/settings-part";
import { footerClass, legalLine, NETWORKS, type Footer } from "../logic/footer";

const stop = (event: { preventDefault: () => void }) => event.preventDefault();

/** Výřez webu s koncem stránky a patičkou v tokenech a `components.css` projektu, markup podle README pro dělníka. */
export default function FooterPreview({ footer, project, theme, componentsCss }: { footer: Footer; project: string; theme: string; componentsCss: string }) {
  return <div className="site-footer__preview" aria-label="Náhled patičky" data-testid="footer-preview">
    <WebStage project={project} theme={theme} componentsCss={componentsCss} name="footer" className="site-footer__stage">
      <div className="ds-container site-footer__page"><p>… konec obsahu stránky.</p></div>
      <footer className={footerClass(footer)}>
        <div className="ds-footer__inner">
          {footer.columns.length > 0 && <div className="ds-footer__columns">
            {footer.columns.map((column, index) => <nav key={index} aria-label={column.title || `Sloupec ${index + 1}`}>
              <h2 className="ds-footer__title">{column.title || "Bez nadpisu"}</h2>
              <ul className="ds-footer__links">{column.links.filter((link) => link.label.trim()).map((link, at) =>
                <li key={at}><a className="ds-footer__link" href={linkHref(link)} onClick={stop}>{link.label}</a></li>)}</ul>
            </nav>)}
          </div>}
          {footer.social.length > 0 && <ul className="ds-footer__social">{footer.social.map((item, index) =>
            <li key={index}><a className="ds-footer__link" href={item.url || "#"} onClick={stop}>{NETWORKS[item.name] ?? item.name}</a></li>)}</ul>}
          <p className="ds-footer__legal">
            <span>{legalLine(footer.legal, new Date().getFullYear())}</span>
            {footer.cookieLink && <a className="ds-footer__link" href="#cookies" onClick={stop}>Nastavení cookies</a>}
          </p>
        </div>
      </footer>
    </WebStage>
  </div>;
}
