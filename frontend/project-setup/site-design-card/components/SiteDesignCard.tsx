import "../styles/site-design-card.css";

/** Část „Design systém webu“ na stránce projektu: co Správa webu je a vstup do ní. Otevření vyřizuje rodič
 *  (`ProjectHome` → App, `projectView=site`); dílek jen hlásí klik. */
export default function SiteDesignCard({ onOpen }: { onOpen: () => void }) {
  return <section className="site-design-card" aria-label="Design systém webu" data-testid="site-design-card">
    <div className="site-design-card__text">
      <h2 className="site-design-card__title">Design systém webu</h2>
      <p className="site-design-card__lead">Jedna globální úroveň webu projektu: barvy s tématy, typografie, mezery, zaoblení a stíny a k tomu nastavení webu. AI z ní vychází při každém vývoji; stránky pak řeší jen detaily.</p>
    </div>
    <button type="button" className="primary site-design-card__open" data-testid="site-design-open" onClick={onOpen}>Otevřít Správu webu</button>
  </section>;
}
