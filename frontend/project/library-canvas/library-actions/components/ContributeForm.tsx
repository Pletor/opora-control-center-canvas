import { useEffect, useState } from "react";
import { loadLibrary, slugOf, type LibraryFolder } from "../../logic/library-api";

/** „Uložit jako vylepšení“ u kopie v projektu: složka knihovny člověka, titulek a slug nového prvku. Prvek ponese
 * rodokmen na tuto kopii a původní prvek uvidí, že z něj vychází. */
export default function ContributeForm({ title, busy, onContribute, onCancel }: {
  title: string; busy: boolean; onContribute: (folder: string, slug: string, title: string) => void; onCancel: () => void;
}) {
  const [folders, setFolders] = useState<LibraryFolder[] | null>(null);
  const [folder, setFolder] = useState("");
  const [name, setName] = useState(`${title} (vylepšení)`);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    loadLibrary("human").then((found) => { if (alive) { setFolders(found); setFolder(found[0]?.id ?? ""); } },
      (cause) => { if (alive) { setFolders([]); setError(cause instanceof Error ? cause.message : String(cause)); } });
    return () => { alive = false; };
  }, []);
  return <form className="library-actions__form" data-testid="library-contribute-form" onSubmit={(event) => { event.preventDefault(); if (folder && name.trim()) onContribute(folder, slugOf(name), name.trim()); }}>
    <label className="library-actions__field">Složka knihovny
      <select className="library-actions__input" value={folder} disabled={!folders} onChange={(event) => setFolder(event.target.value)}>
        {folders?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select></label>
    <label className="library-actions__field">Titulek nového prvku <small className="library-actions__muted">slug {slugOf(name)}</small>
      <input className="library-actions__input" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)}/></label>
    {error && <p className="library-actions__error" role="alert">Knihovnu se nepodařilo načíst: {error}</p>}
    <div className="library-actions__row">
      <button type="submit" className="library-actions__button library-actions__button--primary" disabled={busy || !folder || !name.trim()}>Uložit do knihovny</button>
      <button type="button" className="library-actions__button" onClick={onCancel}>Zrušit</button>
    </div>
  </form>;
}
