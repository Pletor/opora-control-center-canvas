import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { CanonicalRef } from "../logic/knowledge-types";
import type { ResearchDetail } from "../logic/research-types";
/** Full original content is fetched only on demand, pinned to the displayed source revision. */
export default function KnowledgeDetails({ source }: { source: CanonicalRef }) {
  const [detail, setDetail] = useState<ResearchDetail | null>(null);
  const [error, setError] = useState("");
  return <details onToggle={event => {
    if (!event.currentTarget.open || detail) return;
    void api<ResearchDetail>(`/api/research/cards/${encodeURIComponent(source.id)}?` + new URLSearchParams({ project: source.projectId, workspace: source.workspaceId, revision: String(source.revision) }))
      .then(setDetail).catch(reason => setError(String(reason)));
  }}><summary>Podklad a zdroje přesné revize</summary>
    {error && <p role="alert">{error}</p>}
    {detail && <><p>{detail.card.content}</p>{detail.card.sources.map((item,index) => <p key={index}>{item.title} · {item.ref} · {item.quote}</p>)}</>}
  </details>;
}
