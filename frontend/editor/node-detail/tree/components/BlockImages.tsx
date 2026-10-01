// Obrázky jako inspirace: jen reference na cestu (zdroj projektu nebo library/), obsah se nikam nekopíruje.
// Náhled se zkusí načíst přes API zdroje; když soubor není, zůstane popisek a cesta.
import { useState } from "react";
import type { ImageRef } from "@/shared/desktop-state/logic/types";

export default function BlockImages({
  images,
  disabled,
  previewUrl,
  onAdd,
  onRemove,
}: {
  images: ImageRef[];
  disabled: boolean;
  /** URL náhledu pro cestu ve zdroji projektu; null = náhled není k dispozici. */
  previewUrl: (path: string) => string | null;
  onAdd: (path: string, caption: string) => Promise<boolean>;
  onRemove: (imageId: string) => void;
}) {
  const [path, setPath] = useState("");
  const [caption, setCaption] = useState("");
  function submit() {
    const value = path.trim().replace(/\\/g, "/");
    if (!value) return;
    onAdd(value, caption.trim()).then((ok) => { if (ok) { setPath(""); setCaption(""); } });
  }
  return (
    <section className="tree-part" aria-label="Obrázky bloku">
      <h5>Inspirace · {images.length}</h5>
      <ul className="tree-images">
        {images.map((image) => {
          const url = previewUrl(image.path);
          return (
            <li key={image.id}>
              {url ? <img src={url} alt={image.caption || image.path} loading="lazy" /> : <span className="tree-image-missing">bez náhledu</span>}
              <span className="tree-image-meta">
                <span>{image.caption || "(bez popisku)"}</span>
                <code title="Relativní cesta ve zdroji projektu">{image.path}</code>
              </span>
              <button type="button" aria-label="Odebrat obrázek" disabled={disabled} onClick={() => onRemove(image.id)}>✕</button>
            </li>
          );
        })}
      </ul>
      <div className="tree-form">
        <input aria-label="Cesta obrázku" placeholder="docs/mockups/login.png" value={path} disabled={disabled} onChange={(e) => setPath(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }} />
        <input aria-label="Popisek obrázku" placeholder="popisek" value={caption} disabled={disabled} onChange={(e) => setCaption(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }} />
        <button type="button" disabled={disabled || !path.trim()} onClick={submit}>+ Obrázek</button>
      </div>
    </section>
  );
}
