import { formalArtifactUrl, type FormalArtifact, type FormalRecord } from "../logic/formal-verification";
export default function FormalFiles({ record, artifacts, title }: { record: FormalRecord; artifacts: FormalArtifact[]; title: string }) {
  return <section className="formal-verification__files"><h4>{title}</h4>
    {!artifacts.length && <p>V tomto manifestu nejsou soubory.</p>}
    <ul>{artifacts.map(file => <li key={file.path}>
      <div><strong>{file.path}</strong> <span>{file.role} · {file.bytes.toLocaleString("cs-CZ")} B</span></div>
      <code>SHA-256: {file.sha256}</code>
      {file.available === false ? <strong className="formal-verification__warning">Podklad chybí nebo je poškozený; bajty nejsou dostupné.</strong>
        : <a href={formalArtifactUrl(record, record.id, file.sha256)} download>{file.available ? "Stáhnout původní bajty" : "Stáhnout · dostupnost dosud nedoložena"}</a>}
    </li>)}</ul>
    <p className="formal-verification__note">Soubory se stahují jako přílohy. Jejich obsah se v panelu nespouští.</p>
  </section>;
}
