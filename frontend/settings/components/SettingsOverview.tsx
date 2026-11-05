export default function SettingsOverview() {
  return <section className="settings-page__overview" aria-label="Pletor a srdce">
    <p className="settings-page__lead">Společné zázemí organismu, který ovládá Oporu napříč projekty.</p>
    <div className="settings-page__roles">
      <article className="settings-page__card"><span className="settings-page__eyebrow">KOMUNIKACE S ČLOVĚKEM</span><h2>Pletor</h2><p>Přebírá vaše myšlenky, zná kontext pláten a připravuje konkrétní zadání pro srdce. Zpětnou vazbu s vámi převádí do dalšího kroku.</p></article>
      <article className="settings-page__card"><span className="settings-page__eyebrow">RESEARCH A PŘÍPRAVA PRÁCE</span><h2>Srdce / Brain</h2><p>Hledá cesty realizace, ověřuje fakta a rozpadá zadání na úkoly pro tvorbu kódu. Jedno srdce s přehledem napříč projekty.</p></article>
    </div>
    <article className="settings-page__workflow"><span className="settings-page__eyebrow">SAMOSTATNÁ VRSTVA · PLÁTNO 1</span><h2>Jak srdce pracuje</h2><p>Pracovní postupy, rozhodování, delegování a zpětné vazby patří na plátno 1. Tato stránka spravuje prostředky a nastavení, které k tomu organismus používá.</p><p className="muted">Globální workflow srdce naváže v dalším milníku. Současné projektové plátno 1 zůstává dostupné ze stránky projektu.</p></article>
    <p className="muted">Brand a CX/UI/UX vytvářené aplikace patří do design systému jejího repozitáře. Nejsou součástí globální konfigurace organismu.</p>
  </section>;
}
