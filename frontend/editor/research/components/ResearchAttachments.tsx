import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { fileIdBatches, type DrawingFile } from "@/editor/canvas/drawing/logic/drawing-files";
import type { ResearchScope } from "../logic/research-types";
import { safeDrawingPreview } from "../logic/research-model";
export default function ResearchAttachments({ scope, ids }: { scope: ResearchScope; ids: string[] }) {
  const [files, setFiles] = useState<DrawingFile[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const idsKey = JSON.stringify(ids);
  useEffect(() => {
    let alive = true; setFiles([]); setLoading(true); setError("");
    const batches = fileIdBatches([...new Set(ids)]);
    Promise.all(batches.map(batch => api<{ files: DrawingFile[] }>(`/api/drawing-files?${new URLSearchParams({ ...scope, ids: batch.join(",") })}`)))
      .then(results => { if (alive) setFiles(results.flatMap(result => result.files)); })
      .catch(reason => { if (alive) setError(reason instanceof Error ? reason.message : String(reason)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [scope.project, scope.workspace, idsKey]);
  return <section><h3>Vizuální podklady · {ids.length}</h3>{loading && <p role="status">Načítám přílohy…</p>}{error && <p role="alert">{error}</p>}
    {ids.map(id => { const file = files.find(item => item.id === id); const preview = file && safeDrawingPreview(file); return <figure className="research-attachment" key={id}>
      {preview && <a href={preview} download={`podklad-${id}`}><img src={preview} alt={`Vizuální podklad ${id}`} loading="lazy" /></a>}
      <figcaption><code>{id}</code>{!loading && !preview && <span> · Náhled není dostupný{file ? " (nepodporovaný formát)" : ""}.</span>}{preview && <span> · Kliknutím stáhnete originál.</span>}</figcaption>
    </figure>; })}
  </section>;
}
