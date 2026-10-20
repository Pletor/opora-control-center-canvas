import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { EvidenceRequests, evidencePayload, type GitEvidenceContext, type GitEvidenceItem } from "./git-evidence";

type State = { key: string; context: GitEvidenceContext | null; busy: boolean; error: string; notice: string; failedAttempt: boolean };
const empty = (key: string): State => ({ key, context: null, busy: false, error: "", notice: "", failedAttempt: false });
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useGitEvidence(project: string, workspace: string, enabled: boolean, refreshRevision: number) {
  const scope = JSON.stringify([project, workspace]);
  const key = JSON.stringify([project, workspace, enabled, refreshRevision]);
  const active = useRef(key);
  const requests = useRef(new EvidenceRequests());
  const detailRequests = useRef(new EvidenceRequests());
  const writing = useRef(false);
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState(() => empty(key));
  const [attempt, setAttempt] = useState(0);
  const [input, setInput] = useState({ scope, value: "" });
  const [selection, setSelection] = useState({ key, id: "" });
  const shown = state.key === key ? state : empty(key);
  const prNumber = input.scope === scope ? input.value : "";
  const query = new URLSearchParams({ project, workspace }).toString();
  const items = shown.context?.items ?? [];
  const selected = items.find(item => selection.key === key && item.snapshot.id === selection.id) ?? items[0] ?? null;
  const selectedId = selected?.snapshot.id ?? "";
  const detailKey = JSON.stringify([key, selectedId]);
  const detailActive = useRef(detailKey);
  if (detailActive.current !== detailKey) { detailActive.current = detailKey; detailRequests.current.invalidate(); }
  const [detail, setDetail] = useState<{ key: string; item: GitEvidenceItem | null; busy: boolean; error: string }>(
    { key: detailKey, item: null, busy: false, error: "" });
  const shownDetail = detail.key === detailKey ? detail : { key: detailKey, item: null, busy: !!selectedId, error: "" };

  useEffect(() => {
    const valid = detailRequests.current.next();
    if (!enabled || !selectedId) { setDetail({ key: detailKey, item: null, busy: false, error: "" }); return; }
    setDetail({ key: detailKey, item: null, busy: true, error: "" });
    api<GitEvidenceItem>(`/api/oporahub/github-evidence/${encodeURIComponent(selectedId)}?${query}`).then(item => {
      if (valid()) setDetail({ key: detailKey, item, busy: false, error: "" });
    }).catch(error => { if (valid()) setDetail({ key: detailKey, item: null, busy: false, error: message(error) }); });
    return () => detailRequests.current.invalidate();
  }, [detailKey, selectedId, enabled, query, attempt]);

  useEffect(() => {
    const valid = requests.current.next();
    if (!enabled) { setState(empty(key)); return; }
    setState({ ...empty(key), busy: true });
    api<GitEvidenceContext>(`/api/oporahub/github-evidence?${query}`).then(context => {
      if (valid()) setState({ ...empty(key), context });
    }).catch(error => {
      if (valid()) setState({ ...empty(key), error: message(error), failedAttempt: true });
    });
    return () => requests.current.invalidate();
  }, [key, query, enabled, attempt]);

  async function observe() {
    if (!enabled || shown.busy || writing.current || !shown.context?.available) return;
    let payload;
    try { payload = evidencePayload(project, workspace, shown.context.acceptedHead, prNumber); }
    catch (error) { setState({ ...shown, error: message(error) }); return; }
    writing.current = true;
    const valid = requests.current.next();
    setState({ ...shown, busy: true, error: "", notice: "", failedAttempt: false });
    try {
      const item = await api<GitEvidenceItem>("/api/oporahub/github-evidence", payload);
      if (!valid()) return;
      // Earlier evaluations may refer to the previous SHA. Re-read them, never reuse their verdicts.
      const context = { ...shown.context, items: [item] };
      setSelection({ key, id: item.snapshot.id });
      const notice = item.snapshot.complete ? "Pozorování uloženo. GitHub se průběžně neobnovuje." : "Poslední pokus nebyl dokončen. Neúspěch je uložen v historii.";
      try {
        const updated = await api<GitEvidenceContext>(`/api/oporahub/github-evidence?${query}`);
        if (valid()) setState({ ...shown, context: updated, busy: false, error: "", failedAttempt: !item.snapshot.complete, notice });
      } catch (error) {
        if (valid()) setState({ ...shown, context, busy: false, failedAttempt: true, notice,
          error: "Pozorování je uloženo, ale historii se nepodařilo obnovit: " + message(error) });
      }
    } catch (error) {
      if (valid()) setState({ ...shown, busy: false, failedAttempt: true, notice: "",
        error: message(error) + " Pokus se neopakuje automaticky. Obnovte historii před dalším importem." });
    } finally { writing.current = false; }
  }

  return { ...shown, items, selected: shownDetail.item ?? selected, detailBusy: shownDetail.busy, detailError: shownDetail.error, prNumber, project, workspace,
    setPrNumber: (value: string) => setInput({ scope, value }),
    select: (id: string) => setSelection({ key, id }),
    refresh: () => { if (!writing.current) { requests.current.invalidate(); setSelection({ key, id: "" }); setAttempt(value => value + 1); } },
    observe };
}
export type GitEvidenceView = ReturnType<typeof useGitEvidence>;
