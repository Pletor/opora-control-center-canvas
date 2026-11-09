import { useState } from "react";
import { useSiteAdmin } from "../logic/use-site-admin";
import { readSiteSection, type SiteSection } from "../site-menu/logic/site-sections";
import SiteMenu from "../site-menu/components/SiteMenu";
import { TokensStyle } from "../ds-preview/components/TokensScope";
import DsSearch from "../ds-search/components/DsSearch";
import { useHighlight } from "../ds-search/logic/use-highlight";
import SiteProposals from "../site-proposals/components/SiteProposals";
import { useSiteProposals } from "../site-proposals/logic/use-site-proposals";
import SitePanel from "./SitePanel";
import SiteSaveBar from "./SiteSaveBar";
import "../styles/site-admin.css";

/** Správa webu (`projectView=site`): stránka Nastavení webové stránky podle `image9.png`. Rodič drží dokument
 *  projektu, revizi a uložení (Uložit, 409 konflikt), vybranou část a téma náhledu; dílky dostanou hotová data
 *  a změny hlásí nahoru. Kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §1 a §3. */
export default function SiteAdmin({ project, onBack }: { project: string; onBack: () => void }) {
  const state = useSiteAdmin(project);
  const proposals = useSiteProposals(project, state.revision, () => void state.reload());
  const [section, setSection] = useState<SiteSection>(() => readSiteSection(new URLSearchParams(location.search).get("siteSection")));
  const [preview, setPreview] = useState("");
  const [hit, setHit] = useState({ target: "", stamp: 0 });
  useHighlight(hit.target, hit.stamp);
  const themes = state.draft?.design.tokens.color.themes ?? [];
  const theme = themes.some((item) => item.id === preview) ? preview : themes[0]?.id ?? "light";
  const accept = () => { if (!state.dirty || window.confirm("Přijetí návrhu zahodí tvoje neuložené změny. Pokračovat?")) void proposals.accept(); };
  const back = () => { if (!state.dirty || window.confirm("Odejít bez uložení změn Správy webu?")) onBack(); };
  return <section className="site-admin" aria-label="Správa webu" data-testid="site-admin">
    <TokensStyle css={state.tokensCss} project={project}/>
    <header className="site-admin__head">
      <button type="button" className="site-admin__back" onClick={back}>← Architektura</button>
      <h1 className="site-admin__title">Nastavení webové stránky<small className="site-admin__subtitle">{state.draft?.title || "Design systém projektu"} · jedna úroveň pro celý web, AI ji používá při každém vývoji</small></h1>
      {themes.length > 1 && <label className="site-admin__theme">Téma náhledu
        <select className="site-admin__theme-select" value={theme} onChange={(event) => setPreview(event.target.value)}>
          {themes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>}
      <SiteSaveBar revision={state.revision} dirty={state.dirty} saving={state.saving} disabled={!state.draft || state.loading} onSave={state.save}/>
    </header>
    {proposals.proposal && <SiteProposals project={project} proposal={proposals.proposal} busy={proposals.busy} onAccept={accept} onReject={() => void proposals.reject()}/>}
    {proposals.error && <div className="site-admin__alert" role="alert">Návrh srdce: {proposals.error}</div>}
    {state.conflict && <div className="site-admin__alert" role="alert">
      Správu webu mezitím někdo uložil (jiná revize). Tvoje změny jsou zachované.
      <button type="button" className="site-admin__alert-action" onClick={() => void state.overwrite()}>Uložit moje přes ni</button>
      <button type="button" className="site-admin__alert-action" onClick={() => void state.reload()}>Načíst novou a moje zahodit</button>
    </div>}
    {state.error && <div className="site-admin__alert" role="alert">{state.error}<button type="button" className="site-admin__alert-action" onClick={() => void state.reload()}>Načíst znovu</button></div>}
    {!!state.notes.length && <div className="site-admin__notes" role="status">
      <b>Server při uložení upravil:</b>
      <ul className="site-admin__notes-list">{state.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>
      <button type="button" className="site-admin__alert-action" onClick={state.dismissNotes}>Rozumím</button>
    </div>}
    <div className="site-admin__body">
      <SiteMenu value={section} onSelect={setSection} search={state.draft && <DsSearch design={state.draft.design}
        onPick={(found) => { setSection(found.section); setHit({ target: found.target, stamp: Date.now() }); }}/>}/>
      <main className="site-admin__main">
        {state.draft ? <SitePanel section={section} context={{
          project, document: state.draft, revision: state.revision, dirty: state.dirty, theme,
          tokensCss: state.tokensCss, componentsCss: state.componentsCss, notes: state.notes, invalid: state.invalid,
          uploading: state.uploading, uploadError: state.uploadError, change: state.change, upload: (file, record) => void state.upload(file, record),
          uploadAssets: (group, files, record) => void state.uploadAssets(group, files, record), onSelect: setSection,
        }}/> : <p className="site-admin__loading" role="status">{state.loading ? "Načítám Správu webu…" : "Správu webu se nepodařilo načíst."}</p>}
      </main>
    </div>
  </section>;
}
