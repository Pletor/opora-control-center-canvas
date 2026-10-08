import { useState } from "react";
import type { DesignArtifact } from "@/shared/types/logic/types";

export function safeDesignUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return /^https:\/\//i.test(value) && !!url.hostname && !url.username && !url.password &&
      !/[\s\\\u0000-\u001f]/.test(value) && value.length <= 2048;
  } catch { return false; }
}

/** Náhled se načítá jen z https (backend jiný nepřijme); http by prozradilo prohlížení po síti. */
export function safePreviewUrl(value: string | undefined): value is string {
  return !!value && safeDesignUrl(value) && /^https:\/\//i.test(value);
}

export default function CardDesign({ design }: { design: DesignArtifact }) {
  const [failed, setFailed] = useState(false);
  // Obrázek z cizího hostu se nenačte sám: dotaz by prozradil, že člověk kartu právě prohlíží.
  const [shown, setShown] = useState(false);
  if (!safeDesignUrl(design.artifactUrl)) return null;
  const preview = safePreviewUrl(design.previewUrl) ? design.previewUrl : undefined;
  return <div className="nodrag nopan" style={{ padding: "6px 12px" }}>
    <a href={design.artifactUrl} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">
      Návrh · {design.version}
      {preview && shown && !failed &&
        <img src={preview} alt={`Náhled návrhu ${design.version}`} loading="lazy"
          referrerPolicy="no-referrer" onError={() => setFailed(true)}
          style={{ display: "block", maxWidth: "100%", maxHeight: 180, objectFit: "contain" }} />}
    </a>
    {preview && !shown && <button type="button" style={{ marginLeft: 8 }} title="Načte obrázek z adresy náhledu"
      onClick={event => { event.stopPropagation(); setShown(true); }}>Zobrazit náhled</button>}
    {failed && <small>Náhled se nepodařilo načíst. Otevřete odkaz na návrh.</small>}
  </div>;
}
