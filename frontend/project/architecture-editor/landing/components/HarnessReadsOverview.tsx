import type { HarnessOverview, Loaded } from "../logic/component-shelf";

/** Read-only Harness overview: how many worker receipts were scanned and which documentation the workers reported reading.
 *  The reads are reported by workers, not verified by the server; the sentence under the counts says so. */
export default function HarnessReadsOverview({ source }: { source: Loaded<HarnessOverview> }) {
  if (source.error) return <p className="component-shelf__note" role="alert">Přehled Harness se nepodařilo načíst: {source.error}</p>;
  const overview = source.data;
  if (!overview) return <p className="component-shelf__note">Načítám přehled Harness…</p>;
  return <div data-testid="component-shelf-harness">
    <p className="component-shelf__note">Prohledáno {overview.scanned} výsledků dělníků · neplatných {overview.invalid} · v rozporu {overview.conflicts}{overview.limited ? " · jen poslední okno" : ""}. Čtení hlásí dělník, server je nepotvrzuje.</p>
    {overview.reads.length ? <table className="component-shelf__table">
      <thead><tr><th className="component-shelf__th">Zdroj</th><th className="component-shelf__th">Knihovna</th><th className="component-shelf__th">Kdy</th><th className="component-shelf__th">Trvání</th></tr></thead>
      <tbody>{overview.reads.map((read, index) => <tr key={read.resource + read.fetchedAt + index}>
        <td className="component-shelf__td"><code className="component-shelf__code">{read.resource}</code></td><td className="component-shelf__td">{read.library}</td><td className="component-shelf__td">{read.fetchedAt}</td><td className="component-shelf__td">{Math.round(read.durationMs)} ms</td>
      </tr>)}</tbody>
    </table> : <p className="component-shelf__note">Dělníci v tomto prostoru zatím žádné čtení dokumentace neohlásili.</p>}
  </div>;
}
