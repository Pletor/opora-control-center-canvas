import { formalOutcome, formalRevision, formalSourceUrl, type FormalRecord } from "../logic/formal-verification";
import FormalFiles from "./FormalFiles";
export default function FormalDetail({ record, currentAcceptedHead }: { record: FormalRecord; currentAcceptedHead: string | null }) {
  const { verification, report } = record;
  const source = formalSourceUrl(verification.source.repository, verification.source.commitSha);
  return <article className="formal-verification__detail" aria-label="Přesný formální podklad">
    <header><h3>{verification.tool.name === "tlc" ? "TLA+ / TLC" : "Lean"} · {formalOutcome(record)}</h3>
      <p className="formal-verification__trust">Nahlášeno agentem · nezávislé ověření nedoloženo · nepoužitelné pro automatické rozhodnutí o správnosti.</p>
      <p className="formal-verification__note">{formalRevision(record, currentAcceptedHead)}</p></header>
    <dl className="formal-verification__identity">
      <dt>Požadavek</dt><dd><code>{record.id}</code></dd><dt>Karta</dt><dd><code>{record.nodeId}</code></dd>
      <dt>Execution / epocha</dt><dd><code>{record.executionId}</code> / {record.epoch}</dd>
      <dt>Přijatá revize plánu</dt><dd><code>{record.acceptedRevision}</code></dd>
      <dt>Digest zadání</dt><dd><code>{record.assignmentDigest}</code></dd>
      <dt>Digest požadavku</dt><dd><code>{record.requestDigest}</code></dd>
      <dt>Manifest vstupů</dt><dd><code>{record.manifestDigest}</code></dd>
      <dt>Čas přijetí</dt><dd><time dateTime={record.createdAt}>{new Date(record.createdAt).toLocaleString("cs-CZ")}</time></dd>
      <dt>Nahlášený repozitář</dt><dd>{verification.source.repository}</dd>
      <dt>Nahlášený commit</dt><dd>{source ? <a href={source} target="_blank" rel="noopener noreferrer"><code>{verification.source.commitSha}</code></a> : <code>{verification.source.commitSha}</code>}<p>Vazba na zdroj je tvrzení agenta; shoda modelu s tímto commitem nebyla nezávisle ověřena.</p></dd>
      <dt>Nástroj / verze</dt><dd>{verification.tool.name} / {verification.tool.version}</dd>
      <dt>SHA-256 distribuce</dt><dd><code>{verification.tool.distributionSha256}</code></dd>
    </dl>
    <section><h4>Tvrzení</h4><ol className="formal-verification__claims">{verification.claims.map(claim => <li key={claim.id}>
      <strong>{claim.id} · {claim.kind}</strong><p>{claim.statement}</p><code>SHA-256 tvrzení: {claim.statementDigest}</code>
      <span>{report?.checkedClaims.includes(claim.id) ? "Agent nahlásil kontrolu tohoto tvrzení." : "Kontrola tohoto tvrzení není nahlášena."}</span>
    </li>)}</ol></section>
    <section><h4>Předpoklady</h4>{verification.assumptions.length ? <ul>{verification.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul> : <p>Žádné předpoklady nebyly uvedeny; jejich úplnost není ověřena.</p>}</section>
    <section><h4>Konfigurace, konečné meze a režim kontroly</h4><pre>{JSON.stringify(verification.configuration, null, 2)}</pre>
      <p>{verification.tool.name === "tlc" ? "Nahlášené prošlo se vztahuje k uvedenému konečnému modelu a jeho mezím; neprokazuje správnost implementace." : "Samotné sestavení Lean neprokazuje kontrolu proof termů ani tranzitivních axiomů nezávislým ověřovačem."}</p></section>
    <FormalFiles record={record} artifacts={verification.artifacts} title="Vstupní soubory a manifest" />
    <section><h4>Nahlášený výsledek</h4>{report ? <>
      <p><strong>{formalOutcome(record)}</strong> · nahlášeno {new Date(report.createdAt).toLocaleString("cs-CZ")}</p>
      <p className="formal-verification__trust">agent-reported · independentlyVerified: false</p><p>{report.summary}</p>
      <p>Digest výsledku: <code>{report.reportDigest}</code></p><p>Kontrolovaná tvrzení: {report.checkedClaims.join(", ") || "žádná"}</p>
      <FormalFiles record={record} artifacts={report.artifacts} title="Výstupní soubory" />
    </> : <p>Výsledek nebyl nahlášen. Přijetí požadavku samo nespustilo nástroj ani ověřovač.</p>}</section>
  </article>;
}
