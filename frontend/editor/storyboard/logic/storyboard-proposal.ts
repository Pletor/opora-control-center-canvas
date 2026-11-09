import { CONTENT_ROOT, type ContentScope, type ContentProposal } from "@/hub/content-changes/logic/content-changes";
import { parseContentList, parseContentProposal } from "@/hub/content-changes/logic/content-parse";
import type { Storyboard } from "./storyboard-model";

export const storyboardReviewLink = (scope: ContentScope, id: string) => "/?" + new URLSearchParams({
  ...scope, environment: "hub", ohContent: id });
const canonical = (value: unknown) => JSON.stringify(value, (_, item) => item && typeof item === "object" && !Array.isArray(item)
  ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
/** Propose the exact saved native source, then use the existing content review. Never accepts. */
export async function proposeStoryboard(scope: ContentScope, nodeId: string, revision: number,
  api: <T>(url: string, body?: object) => Promise<T>): Promise<ContentProposal> {
  const source = await api<{ revision: number; storyboard: Storyboard | null }>("/api/storyboard?" + new URLSearchParams({ ...scope, nodeId }));
  if (source.revision !== revision) throw new Error("Storyboard se změnil. Načtěte aktuální revizi před návrhem.");
  const list = parseContentList(await api(CONTENT_ROOT + "?" + new URLSearchParams(scope)));
  if (list.readOnly || !list.acceptedHead) throw new Error("Nejprve je potřeba přijatý plán v pracovním prostoru.");
  const proposal = parseContentProposal(await api(CONTENT_ROOT, { ...scope, expectedAcceptedHead: list.acceptedHead,
    subject: `Přijetí Storyboardu · ${source.storyboard?.title || nodeId}`.slice(0, 200),
    changes: [{ kind: "storyboard", target: nodeId, field: "storyboard", value: source.storyboard }] }), scope);
  const change = proposal.changes[0];
  if (change.observedRevision !== revision || canonical(change.before) !== canonical(source.storyboard))
    throw new Error("Zdroj se během přípravy změnil. Návrh nebyl přijat; obnovte Storyboard a zkontrolujte změny obsahu.");
  return proposal;
}
