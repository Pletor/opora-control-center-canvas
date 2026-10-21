import { useEffect, useRef, useState } from "react";
import { api, type CanvasNode } from "@/shared/types/logic/types";
import { ProposalRequests, proposalPayload, type ProposalContext, type ProposalRecord, type ProposalDiff } from "./proposals";

type State = { key: string; context: ProposalContext | null; items: ProposalRecord[];
  diff: ProposalDiff | null; busy: boolean; error: string; notice: string };
const empty = (key: string): State => ({ key, context: null, items: [], diff: null, busy: false, error: "", notice: "" });
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function useOporaProposals(project: string, workspace: string, nodes: CanvasNode[], enabled: boolean, readOnly: boolean) {
  const choices = nodes.filter(n => ["area", "sector", "node"].includes(n.kind));
  const owner = JSON.stringify([project, workspace]);
  const [selection, setSelection] = useState({ owner, id: "" });
  const scope = selection.owner === owner && choices.some(n => n.id === selection.id)
    ? selection.id : choices[0]?.id ?? "";
  const key = JSON.stringify([project, workspace, scope, enabled]);
  const currentKey = useRef(key);
  const requests = useRef(new ProposalRequests());
  const writing = useRef(false);
  if (currentKey.current !== key) {
    currentKey.current = key;
    requests.current.invalidate();
  }
  const [state, setState] = useState<State>(() => empty(key));
  const [attempt, setAttempt] = useState(0);
  const [subjectValue, setSubjectValue] = useState({ key, text: "" });
  const subject = subjectValue.key === key ? subjectValue.text : "";
  const shown = state.key === key ? state : empty(key);
  const query = new URLSearchParams({ project, workspace, scope }).toString();

  useEffect(() => {
    const valid = requests.current.next();
    if (!enabled || !scope) { setState(empty(key)); return; }
    setState({ ...empty(key), busy: true });
    Promise.all([
      api<ProposalContext>(`/api/oporahub/context?${query}`),
      api<{ items: ProposalRecord[] }>(`/api/opora-commits?${query}&limit=100`),
    ]).then(([context, history]) => {
      if (valid()) setState({ ...empty(key), context, items: history.items });
    }).catch(error => {
      if (valid()) setState({ ...empty(key), error: message(error) });
    });
    return () => requests.current.invalidate();
  }, [key, query, enabled, scope, attempt]);

  async function create() {
    if (!shown.context || !subject.trim() || shown.busy || readOnly || writing.current) return;
    writing.current = true;
    const valid = requests.current.next();
    const payload = proposalPayload(project, workspace, scope, subject, shown.context);
    setState({ ...shown, busy: true, error: "", notice: "" });
    try {
      await api("/api/oporahub/proposals", payload);
      if (!valid()) return;
      // Do not silently acquire a newer assignment after a write; refresh is explicit.
      const history = await api<{ items: ProposalRecord[] }>(`/api/opora-commits?${query}&limit=100`);
      if (valid()) setState({ ...shown, context: null, diff: null, items: history.items, busy: false,
        error: "", notice: "Návrh uložen. Před dalším návrhem obnovte kontext." });
    } catch (error) {
      if (valid()) setState({ ...shown, context: null, busy: false,
        error: message(error) + " Obnovte kontext a zkontrolujte historii před dalším zápisem." });
    } finally { writing.current = false; }
  }

  async function compare(before: string, after: string) {
    if (!before || !after || shown.busy || writing.current) return;
    const valid = requests.current.next();
    setState({ ...shown, busy: true, diff: null, error: "" });
    try {
      const diff = await api<ProposalDiff>(`/api/oporahub/diff?${query}&${new URLSearchParams({ before, after })}`);
      if (valid()) setState({ ...shown, busy: false, error: "", diff });
    } catch (error) {
      if (valid()) setState({ ...shown, busy: false, diff: null, error: message(error) });
    }
  }

  return { ...shown, scope, choices, subject, readOnly,
    select: (id: string) => setSelection({ owner, id }),
    setSubject: (text: string) => setSubjectValue({ key, text }),
    refresh: () => { if (!writing.current) { requests.current.invalidate(); setAttempt(n => n + 1); } },
    create, compare };
}
export type OporaProposalsView = ReturnType<typeof useOporaProposals>;
