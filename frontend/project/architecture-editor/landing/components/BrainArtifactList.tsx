import { shortVersion, type BrainArtifact, type Loaded } from "../logic/component-shelf";

/** Read-only list of Brain artifacts of one kind: ID, active version and its status. Editing the Brain is a later milestone. */
export default function BrainArtifactList({ artifacts, source }: { artifacts: BrainArtifact[]; source: Loaded<BrainArtifact[]> }) {
  if (source.error) return <p className="component-shelf__note" role="alert">Registr Brainu se nepodařilo načíst: {source.error}</p>;
  if (!source.data) return <p className="component-shelf__note">Načítám registr Brainu…</p>;
  if (!artifacts.length) return <p className="component-shelf__note">V registru Brainu zatím žádný artefakt tohoto druhu není.</p>;
  return <table className="component-shelf__table" data-testid="component-shelf-brain">
    <thead><tr><th className="component-shelf__th">ID</th><th className="component-shelf__th">Verze</th><th className="component-shelf__th">Stav</th></tr></thead>
    <tbody>{artifacts.map((artifact) => <tr key={artifact.id}>
      <td className="component-shelf__td"><code className="component-shelf__code">{artifact.id}</code></td>
      <td className="component-shelf__td" title={artifact.active?.version}>{artifact.active ? shortVersion(artifact.active.version) : "–"}</td>
      <td className="component-shelf__td">{artifact.active ? artifact.active.status : "bez aktivní verze"}</td>
    </tr>)}</tbody>
  </table>;
}
