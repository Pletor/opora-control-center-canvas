import { useState, type ClipboardEvent, type DragEvent } from "react";
import type { SectionInspiration } from "@/shared/types/logic/types";
import { uploadImage } from "@/editor/storyboard/logic/sketch-files";
import { addInspirationFiles, INSPIRATION_MAX_FILES, INSPIRATION_NOTE_MAX, inspirationRejects, inspirationUrlError, removeInspirationFile } from "../logic/box-detail";
import { useInspirationFiles } from "../logic/use-inspiration-files";

type Props = {
  project: string; workspace: string; inspiration: SectionInspiration | undefined;
  /** Proč inspiraci nejde měnit (zámek obsahu, Git main); `null` = jde. */
  lock: string | null;
  onChange: (inspiration: SectionInspiration) => void;
};

/** Inspirace boxu: 0–6 obrázků (Ctrl+V do zóny, přetažení, výběr souboru) nahraných přes `/api/drawing-file`, náhledy
 * s klikem na zvětšení, odkaz na web a poznámka. Dílek nahraje obrázky a hlásí novou inspiraci nahoru; ukládá rodič. */
export default function BoxInspiration({ project, workspace, inspiration, lock, onChange }: Props) {
  const files = inspiration?.files ?? [];
  const { previews, error: loadError } = useInspirationFiles(project, workspace, files);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState<string | null>(null);
  async function add(list: File[]) {
    if (lock || busy || !list.length) return;
    setError("");
    const accepted: File[] = [];
    for (const file of list) { const reason = inspirationRejects(file, files.length + accepted.length); if (reason) { setError(reason); break; } accepted.push(file); }
    if (!accepted.length) return;
    setBusy(true);
    try { onChange(addInspirationFiles(inspiration, await Promise.all(accepted.map((file) => uploadImage(project, workspace, file, file.type))))); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  const paste = (event: ClipboardEvent) => { const list = [...event.clipboardData.files]; if (list.length) { event.preventDefault(); void add(list); } };
  const drop = (event: DragEvent) => { event.preventDefault(); void add([...event.dataTransfer.files]); };
  /** Odkaz a poznámka se ukládají každý zvlášť při opuštění pole; neplatný odkaz se neuloží a řekne proč. */
  function commit(key: "url" | "note", value: string) {
    const reason = key === "url" ? inspirationUrlError(value) : null;
    setError(reason ?? "");
    if (!reason && value.trim() !== (inspiration?.[key] ?? "")) onChange({ ...inspiration, [key]: value.trim() });
  }
  const safeUrl = inspiration?.url && !inspirationUrlError(inspiration.url) ? inspiration.url : null;
  return <section className="box-detail__block" aria-label="Inspirace">
    <h4 className="box-detail__block-title">Inspirace <small>{files.length}/{INSPIRATION_MAX_FILES}</small></h4>
    {files.length > 0 && <div className="box-detail__thumbs">
      {files.map((id) => <figure key={id} className="box-detail__thumb">
        {previews.get(id) ? <button type="button" className="box-detail__thumb-open" aria-label="Zvětšit obrázek" onClick={() => setZoom(previews.get(id)!)}><img src={previews.get(id)} alt="Inspirace"/></button>
          : <span className="box-detail__hint">…</span>}
        {!lock && <button type="button" className="box-detail__thumb-remove" aria-label="Odebrat obrázek" onClick={() => onChange(removeInspirationFile(inspiration, id))}>✕</button>}
      </figure>)}
    </div>}
    {lock ? <p className="box-detail__hint">{lock}</p>
      : files.length < INSPIRATION_MAX_FILES && <div className="box-detail__drop" tabIndex={0} aria-label="Vložit obrázek inspirace (Ctrl+V nebo přetažení)" data-testid="architecture-box-inspiration-drop"
        onPaste={paste} onDragOver={(event) => event.preventDefault()} onDrop={drop}>
        {busy ? "Nahrávám…" : <>Klikněte a Ctrl+V, přetáhněte obrázek, nebo <label className="box-detail__file">vyberte soubor<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple hidden
          onChange={(event) => { void add([...(event.target.files ?? [])]); event.target.value = ""; }}/></label></>}
      </div>}
    <label className="box-detail__field">Odkaz na web
      <input type="url" key={inspiration?.url} defaultValue={inspiration?.url} disabled={!!lock} placeholder="https://…" maxLength={2048} onBlur={(event) => commit("url", event.target.value)}/></label>
    {safeUrl && <a className="box-detail__link" href={safeUrl} target="_blank" rel="noreferrer noopener">Otevřít odkaz ↗</a>}
    <label className="box-detail__field">Poznámka
      <input key={inspiration?.note} defaultValue={inspiration?.note} disabled={!!lock} maxLength={INSPIRATION_NOTE_MAX} placeholder="Co z inspirace převzít" onBlur={(event) => commit("note", event.target.value)}/></label>
    {(error || loadError) && <p className="box-detail__error" role="alert">{error || loadError}</p>}
    {zoom && <div className="box-detail__zoom" role="dialog" aria-label="Inspirace zvětšená" tabIndex={-1} ref={(element) => element?.focus()}
      onClick={() => setZoom(null)} onKeyDown={(event) => { if (event.key === "Escape") setZoom(null); }}>
      <img src={zoom} alt="Inspirace zvětšená"/>
    </div>}
  </section>;
}
