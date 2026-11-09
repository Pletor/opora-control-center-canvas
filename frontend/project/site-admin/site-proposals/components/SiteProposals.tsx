import { useState } from "react";
import { attachmentUrl, diffLines, downloadAttachment, type SiteProposal } from "../logic/site-proposals";
import "../styles/site-proposals.css";

/** Pruh „Srdce navrhuje změnu“ nad obsahem Správy webu: poznámka srdce, rozdíl po polích a Přijmout / Zamítnout.
 *  Dílek jen ukazuje; přijetí i zamítnutí hlásí nahoru, zapisuje rodič `SiteAdmin`. */
export default function SiteProposals({ project, proposal, busy, onAccept, onReject }: {
  project: string; proposal: SiteProposal; busy: boolean; onAccept: () => void; onReject: () => void;
}) {
  const lines = diffLines(proposal);
  const [downloadError, setDownloadError] = useState("");
  const more = proposal.diffTotal - lines.length;
  return <section className="site-proposals" aria-label="Návrh změny od srdce" data-testid="site-proposal">
    <div className="site-proposals__head">
      <b className="site-proposals__title">Srdce navrhuje změnu</b>
      <span className="site-proposals__meta">nad revizí {proposal.baseRevision}{proposal.note ? ` · ${proposal.note}` : ""}</span>
      <button type="button" className="primary" disabled={busy} onClick={onAccept}>{proposal.recoveryNeeded ? "Dokončit přerušené přijetí" : "Přijmout"}</button>
      <button type="button" className="site-proposals__reject" disabled={busy || proposal.recoveryNeeded} onClick={onReject}>Zamítnout</button>
    </div>
    <ul className="site-proposals__diff">
      {lines.map((line) => <li key={line.path} className="site-proposals__change">
        <code className="site-proposals__path">{line.path}</code>
        <span className="site-proposals__before">{line.before}</span>
        <span className="site-proposals__after">{line.after}</span>
      </li>)}
      {more > 0 && <li className="site-proposals__more">… a další změny ({more})</li>}
    </ul>
    {!!proposal.attachments?.length && <div aria-label="Přílohy návrhu">
      <p>{proposal.recoveryNeeded ? "Stažení ukazuje navržený obsah. Skutečný stav přerušeného přijetí je uveden níže."
        : "Přílohy čekají na přijetí. Stažení ukazuje navržený obsah; živé soubory se změní až po přijetí."}</p>
      <ul>{proposal.attachments.map((item, index) => <li key={item.path}>
        <b>{item.op === "delete" ? "Odstranit" : item.baseDigest ? "Nahradit" : "Přidat"}</b>{" "}<code>{item.path}</code>
        {item.op === "put" && <> · {item.size.toLocaleString("cs-CZ")} B · {item.type}{" "}
          <a href={attachmentUrl(project, proposal.id, index)} download={item.name} onClick={event => {
            event.preventDefault(); setDownloadError("");
            void downloadAttachment(attachmentUrl(project, proposal.id, index), item.name)
              .catch(error => setDownloadError(String(error)));
          }}>Stáhnout navržený soubor</a></>}
        <div>SHA-256 před: <code>{item.baseDigest ?? "soubor neexistuje"}</code></div>
        {item.sha256 && <div>SHA-256 po: <code>{item.sha256}</code></div>}
      </li>)}</ul>
    </div>}
    {downloadError && <p role="alert">{downloadError}</p>}
    {proposal.recoveryNeeded && <div role="alert">
      <b>Přijetí bylo přerušeno. Některé soubory už mohou být změněné.</b>
      <p>Dokončení ověří každý původní i nový otisk. Cizí změnu nepřepíše.</p>
      <ul>{proposal.recoveryTargets?.map(item => <li key={item.path}><code>{item.path}</code>: {
        item.state === "after" ? "nový obsah uložen" : item.state === "before" ? "původní obsah" : "konflikt s jinou změnou"
      }</li>)}</ul>
    </div>}
  </section>;
}
