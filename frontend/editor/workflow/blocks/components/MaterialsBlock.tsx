// Blok Podklady: obrázky (nahrané do složky projektu), cesty ve zdroji projektu a URL, které agent dostane
// jako podklad. Přetažení / vložení / výběr souboru drží lokálně; každé uložení bublá nahoru callbackem.
import { useRef, useState, type DragEvent, type ClipboardEvent } from "react";
import type { NodeMaterial } from "@/shared/desktop-state/logic/types";

export type MaterialHandlers = {
  previewUrl: (material: NodeMaterial) => string | null;
  onMove: (index: number, delta: number) => void;
  onRemove: (material: NodeMaterial) => void;
  onCaption: (id: string, caption: string) => void;
  /** Cesta ve zdroji projektu nebo http(s) URL. */
  onAddRef: (path: string, caption: string) => Promise<boolean>;
  /** Obrázek jako data URL; rodič ho nahraje a zapíše do stavu. */
  onUpload: (dataUrl: string, caption: string) => Promise<boolean>;
};

export const MATERIAL_KIND_LABEL: Record<NodeMaterial["kind"], string> = { upload: "nahráno", source: "zdroj", link: "odkaz" };

/** Soubory z drop / paste / výběru převedené na data URL; jen obrázky. */
export function imageFiles(list: FileList | DataTransferItemList | null | undefined): File[] {
  const files: File[] = [];
  if (!list) return files;
  for (let i = 0; i < list.length; i += 1) {
    const item = list[i] as File | DataTransferItem;
    const file = item instanceof File ? item : item.kind === "file" ? item.getAsFile() : null;
    if (file && file.type.startsWith("image/")) files.push(file);
  }
  return files;
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Soubor se nepodařilo přečíst."));
    reader.readAsDataURL(file);
  });
}

export default function MaterialsBlock({
  materials,
  disabled,
  readOnly,
  previewUrl,
  onMove,
  onRemove,
  onCaption,
  onAddRef,
  onUpload,
}: { materials: NodeMaterial[]; disabled: boolean; readOnly: boolean } & MaterialHandlers) {
  const [path, setPath] = useState("");
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const picker = useRef<HTMLInputElement>(null);

  async function upload(files: File[]) {
    if (disabled) return;
    if (!files.length) { setError("Vložte obrázek (png, jpg, gif, webp, svg)."); return; }
    setError("");
    for (const file of files) {
      if (file.size > 8 * 1024 * 1024) { setError(`${file.name}: větší než 8 MB.`); continue; }
      const ok = await onUpload(await readAsDataUrl(file), file.name.replace(/\.[^.]+$/, ""));
      if (!ok) setError(`${file.name}: nepodařilo se uložit.`);
    }
  }
  function submitRef() {
    const value = path.trim();
    if (!value) return;
    onAddRef(value, "").then((ok) => { if (ok) { setPath(""); setError(""); } });
  }
  const drop = (e: DragEvent) => { e.preventDefault(); setDragging(false); void upload(imageFiles(e.dataTransfer.files)); };
  const paste = (e: ClipboardEvent) => {
    const files = imageFiles(e.clipboardData.items);
    if (files.length) { e.preventDefault(); void upload(files); }
  };

  return (
    <>
      <ol className="block-materials">
        {materials.map((material, index) => {
          const url = previewUrl(material);
          return (
            <li key={material.id}>
              {url ? <img src={url} alt={material.caption || material.path} /> : <span className="material-thumb-missing">{material.kind === "link" ? "URL" : "cesta"}</span>}
              <span className="block-label">
                <input
                  aria-label="Popisek podkladu"
                  placeholder="K čemu je tento podklad…"
                  defaultValue={material.caption}
                  disabled={readOnly}
                  onKeyDown={(e) => { e.stopPropagation(); if (e.key === "Enter") e.currentTarget.blur(); }}
                  onBlur={(e) => { if (e.currentTarget.value !== material.caption) onCaption(material.id, e.currentTarget.value); }}
                />
                <small>
                  {MATERIAL_KIND_LABEL[material.kind]} ·{" "}
                  {material.kind === "link" ? <a href={material.path} target="_blank" rel="noreferrer">{material.path}</a> : material.path}
                </small>
              </span>
              <span className="block-tools">
                <button type="button" aria-label="Posunout výš" disabled={disabled || index === 0} onClick={() => onMove(index, -1)}>▲</button>
                <button type="button" aria-label="Posunout níž" disabled={disabled || index === materials.length - 1} onClick={() => onMove(index, 1)}>▼</button>
                <button type="button" aria-label="Odebrat podklad" disabled={disabled} onClick={() => onRemove(material)}>✕</button>
              </span>
            </li>
          );
        })}
      </ol>
      <div
        className={"block-dropzone" + (dragging ? " is-dragging" : "") + (disabled ? " is-disabled" : "")}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Přidat obrázek: přetáhnout, vložit ze schránky nebo vybrat soubor"
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
        onPaste={paste}
        onClick={() => { if (!disabled) picker.current?.click(); }}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); picker.current?.click(); } }}
      >
        Přetáhněte obrázek, vložte ze schránky (Ctrl+V) nebo klikněte a vyberte soubor
        <input ref={picker} type="file" accept="image/*" multiple hidden onChange={(e) => { void upload(imageFiles(e.currentTarget.files)); e.currentTarget.value = ""; }} />
      </div>
      <div className="block-form">
        <input
          aria-label="Cesta ve zdroji projektu nebo URL"
          placeholder="docs/schema.png nebo https://…"
          value={path}
          disabled={readOnly}
          onChange={(e) => setPath(e.target.value)}
          onKeyDown={(e) => { e.stopPropagation(); if (e.key === "Enter") submitRef(); }}
        />
        <button type="button" className="block-add" disabled={disabled || !path.trim()} onClick={submitRef}>+ Odkaz</button>
      </div>
      {error && <p className="block-error" role="alert">{error}</p>}
    </>
  );
}
