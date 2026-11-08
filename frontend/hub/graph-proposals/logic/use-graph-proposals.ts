import { useEffect, useRef, useState } from "react";
import { api, type CanvasNode } from "@/shared/types/logic/types";
import { trackSaveWrite } from "@/shared/hooks/logic/save-coordinator";
import { postGraphProposal } from "./graph-api";
import { scopedProposalLink } from "./proposal-preview";
import { graphEditPayload } from "./graph-edits";
import { useGraphEdits } from "./use-graph-edits";
import { flashEnded, flashFor, flashModifier, type DecisionFlash } from "./decision-flash";
import { adoptionKey, GraphRequests, graphActionPayload, graphPayload, graphReadState, newDraftNode,
  type DraftEdge, type DraftNode, type GraphContext, type GraphProposal, type GraphSummary } from "./graph-proposals";

type State = { key: string; context: GraphContext | null; items: GraphSummary[]; busy: boolean; error: string; notice: string };
const empty = (key: string): State => ({ key, context: null, items: [], busy: false, error: "", notice: "" });
const message = (error: unknown) => error instanceof Error ? error.message : String(error);
const ROOT = "/api/oporahub/graph-proposals";
export function useGraphProposals(project: string, workspace: string, existing: CanvasNode[], enabled: boolean,
  readOnly: boolean, refreshRevision: number, onApplied: () => void) {
  const scope = JSON.stringify([project, workspace]);
  const key = JSON.stringify([scope, enabled, refreshRevision]);
  const active = useRef(key), requests = useRef(new GraphRequests()), details = useRef(new GraphRequests());
  const nodeSequence = useRef(1);
  if (active.current !== key) { active.current = key; requests.current.invalidate(); details.current.invalidate(); }
  const [state, setState] = useState(() => empty(key));
  const [writePending, setWritePending] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [selection, setSelection] = useState({ key, id: "" });
  const [ack, setAck] = useState({ key: "", value: "" });
  const [flash, setFlash] = useState<DecisionFlash>(null);
  const [draft, setDraft] = useState({ scope, subject: "", nodes: [newDraftNode("new1")], edges: [] as DraftEdge[] });
  const form = draft.scope === scope ? draft : { scope, subject: "", nodes: [newDraftNode("new1")], edges: [] as DraftEdge[] };
  const shown = state.key === key ? state : empty(key);
  const edits = useGraphEdits(JSON.stringify([key, attempt, shown.context?.graphDigest, shown.context?.acceptedHead]), shown.context);
  const linkedId = scopedProposalLink(typeof location === "undefined" ? "" : location.search, project, workspace);
  const selectedId = selection.key === key && selection.id ? selection.id : linkedId;
  const detailKey = JSON.stringify([key, selectedId, attempt]);
  const detailActive = useRef(detailKey);
  if (detailActive.current !== detailKey) { detailActive.current = detailKey; details.current.invalidate(); }
  const [detail, setDetail] = useState<{ key: string; item: GraphProposal | null; busy: boolean; error: string }>(
    { key: detailKey, item: null, busy: false, error: "" });
  const inspected = detail.key === detailKey ? detail.item : null;
  const query = new URLSearchParams({ project, workspace }).toString();
  const acknowledgement = ack.key === detailKey ? ack.value : "";
  const disabled = shown.busy || writePending || readOnly || !!shown.context?.readOnly || !shown.context;

  useEffect(() => {
    const valid = requests.current.next();
    setAck({ key: "", value: "" });
    if (!enabled) { setState(empty(key)); return; }
    setState({ ...empty(key), busy: true });
    Promise.allSettled([api<GraphContext>(`${ROOT}/context?${query}`), api<{ items: GraphSummary[]; acceptedHead: string | null }>(`${ROOT}?${query}`)])
      .then(([loaded, history]) => {
        if (!valid()) return;
        setState({ ...empty(key), ...graphReadState(loaded, history) });
      });
    return () => requests.current.invalidate();
  }, [key, query, enabled, attempt]);

  useEffect(() => {
    const valid = details.current.next();
    setAck({ key: "", value: "" });
    if (!enabled || !selectedId) { setDetail({ key: detailKey, item: null, busy: false, error: "" }); return; }
    setDetail({ key: detailKey, item: null, busy: true, error: "" });
    api<GraphProposal>(`${ROOT}/${encodeURIComponent(selectedId)}?${query}`).then(item => {
      if (valid()) setDetail({ key: detailKey, item, busy: false, error: "" });
    }).catch(error => { if (valid()) setDetail({ key: detailKey, item: null, busy: false, error: message(error) }); });
    return () => details.current.invalidate();
  }, [detailKey, selectedId, query, enabled]);

  async function write(path: string, payload: object, action: "create" | "accept" | "rebase") {
    if (disabled || !enabled) return;
    const valid = requests.current.beginWrite();
    if (!valid) return;
    setWritePending(true);
    details.current.invalidate(); setAck({ key: "", value: "" }); setFlash(null);
    setState({ ...shown, busy: true, error: "", notice: "" });
    try {
      const mutation = postGraphProposal<{ id: string }>(path, payload);
      const result = await (action === "accept" ? trackSaveWrite(project, workspace, mutation) : mutation);
      // Parent checks captured scope even when this panel was left during the mutation.
      if (action === "accept") onApplied();
      if (!valid()) return;
      if (action === "accept") setFlash(flashFor(selectedId, "accepted"));
      setState({ ...shown, context: null, busy: false, error: "", notice: action === "accept"
        ? "Rozšíření plánu přijato. Canvas se obnovuje; nejde o ověření implementace."
        : "Neměnný návrh uložen. Před dalším krokem obnovte kontext a prohlédněte jeho obsah." });
      setDetail({ key: detailKey, item: null, busy: false, error: "" });
      if (action === "create") { setDraft({ scope, subject: "", nodes: [newDraftNode("new1")], edges: [] }); edits.reset(); }
      setSelection({ key, id: action === "accept" ? selectedId : result.id });
      setAttempt(value => value + 1);
    } catch (error) {
      if (valid() && action === "accept") setFlash(flashFor(selectedId, "refused"));
      if (valid()) { setState({ ...shown, context: null, busy: false, notice: "", error: message(error) + " Obnovte kontext a zkontrolujte historii; akce se automaticky neopakuje." });
        setDetail({ key: detailKey, item: null, busy: false, error: "" }); }
    } finally { requests.current.endWrite(); setWritePending(false); }
  }
  function action(kind: "create" | "accept" | "rebase") {
    if (disabled || !shown.context) return;
    try {
      if (kind === "create") void write(ROOT, graphPayload(project, workspace, form.subject, shown.context, form.nodes, form.edges), kind);
      else if (inspected) void write(`${ROOT}/${encodeURIComponent(inspected.id)}/${kind}`,
        graphActionPayload(project, workspace, shown.context, inspected, kind, acknowledgement), kind);
    } catch (error) { setState({ ...shown, error: message(error) }); }
  }
  function createChanges(adoptionOnly = false) {
    if (disabled || !shown.context) return;
    try {
      const payload = adoptionOnly
        ? { project, workspace, subject: form.subject.trim() || "Převzetí stávajícího grafu", parentRevision: shown.context.acceptedHead,
          expectedGraphDigest: shown.context.graphDigest, plan: { nodes: [], edges: [] } }
        : graphEditPayload(project, workspace, form.subject, shown.context, edits.draft);
      void write(ROOT, payload, "create");
    } catch (error) { setState({ ...shown, error: message(error) }); }
  }
  return { ...shown, busy: shown.busy || writePending, form, existing, inspected, disabled, edits,
    createChanges: () => createChanges(), adoptExisting: () => createChanges(true),
    detailBusy: detail.key !== detailKey ? !!selectedId : detail.busy,
    detailError: detail.key === detailKey ? detail.error : "",
    acknowledged: !!inspected && acknowledgement === adoptionKey(inspected),
    acknowledge: (checked: boolean) => setAck({ key: detailKey, value: checked && inspected ? adoptionKey(inspected) : "" }),
    inspect: (id: string) => { if (!requests.current.busy) { details.current.invalidate(); setAck({ key: "", value: "" }); setFlash(null); setSelection({ key, id }); } },
    flashOf: (id: string) => flashModifier(flash, id),
    endFlash: (id: string) => setFlash(current => flashEnded(current, id)),
    refresh: () => { if (!requests.current.busy) { setFlash(null); requests.current.invalidate(); details.current.invalidate(); setAck({ key: "", value: "" }); setAttempt(value => value + 1); } },
    editSubject: (subject: string) => setDraft({ ...form, subject }),
    editNode: (index: number, field: keyof DraftNode, value: string) => setDraft({ ...form, nodes: form.nodes.map((node, i) => i === index ? { ...node, [field]: value } : node) }),
    addNode: () => { const ref = `new${++nodeSequence.current}`; setDraft({ ...form, nodes: [...form.nodes, newDraftNode(ref)] }); },
    removeNode: (index: number) => setDraft({ ...form, nodes: form.nodes.filter((_, i) => i !== index) }),
    addEdge: () => setDraft({ ...form, edges: [...form.edges, { from: "", to: "", carries: "" }] }),
    editEdge: (index: number, field: keyof DraftEdge, value: string) => setDraft({ ...form, edges: form.edges.map((edge, i) => i === index ? { ...edge, [field]: value } : edge) }),
    removeEdge: (index: number) => setDraft({ ...form, edges: form.edges.filter((_, i) => i !== index) }),
    create: () => action("create"), accept: () => action("accept"), rebase: () => action("rebase") };
}
export type GraphProposalsView = ReturnType<typeof useGraphProposals>;
