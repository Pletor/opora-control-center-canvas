import { useEffect, useRef, useState } from "react";
import { api, type CanvasNode, type SpecFields } from "@/shared/types/logic/types";
import { ProposalRequests } from "@/hub/proposal-history/logic/proposals";
import { changesetPayload, type PlanContext, type PlanChangeset, type PlanDocument } from "./plan-changes";
import { samePinnedDocuments } from "./baseline-review";

type BaselinePreparation = { operationId: string; documents: PlanDocument[]; payload: { project: string; workspace: string; subject: string; expectedAcceptedHead: null; expectedGraphDigest: string; expectedSpecificationsVersion: string } };
type State = { key: string; context: PlanContext | null; items: PlanChangeset[]; busy: boolean; error: string; notice: string; preparation?: BaselinePreparation };
const empty = (key: string): State => ({ key, context: null, items: [], busy: false, error: "", notice: "" });
const message = (e: unknown) => e instanceof Error ? e.message : String(e);
export function selectedPlanDocument(documents: PlanDocument[], selection: { key: string; node: string }, key: string) {
  return selection.key === key && selection.node ? documents.find(item => item.nodeId === selection.node) : documents[0];
}
export function refreshedPlanSelection(selection: { key: string; node: string }, key: string) {
  return { key, node: selection.key === key ? selection.node : "", proposal: "" };
}

export function usePlanChanges(project: string, workspace: string, nodes: CanvasNode[], enabled: boolean,
  readOnly: boolean, onApplied: () => void) {
  const key = JSON.stringify([project, workspace, enabled]);
  const current = useRef(key);
  const requests = useRef(new ProposalRequests());
  const writing = useRef(false);
  if (current.current !== key) { current.current = key; requests.current.invalidate(); }
  const [state, setState] = useState(() => empty(key));
  const shown = state.key === key ? state : empty(key);
  const [attempt, setAttempt] = useState(0);
  const [selection, setSelection] = useState({ key, node: "", proposal: "" });
  const [draft, setDraft] = useState<{ key: string; node: string; fields: SpecFields } | null>(null);
  const [title, setTitle] = useState({ key, text: "" });
  const route = new URLSearchParams(typeof location === "undefined" ? "" : location.search);
  const linkedScope = route.get("project") === project && route.get("workspace") === workspace;
  const baselineId = linkedScope ? route.get("ohBaseline") : null;
  const changesetId = linkedScope ? route.get("ohChangeset") : null;
  const preparation = shown.preparation;
  const subject = baselineId ? preparation?.payload.subject ?? "" : title.key === key ? title.text : "";
  const context = shown.context;
  const preparationMatches = !baselineId || !!preparation && preparation.operationId === baselineId && !!context
    && context.acceptedHead === null && context.graphDigest === preparation.payload.expectedGraphDigest
    && context.specificationsVersion === preparation.payload.expectedSpecificationsVersion
    && samePinnedDocuments(context.documents, preparation.documents);
  const documents = context?.documents ?? [];
  const document = selectedPlanDocument(documents, selection, key);
  const missingDocument = selection.key === key && selection.node && !document ? selection.node : null;
  const fields = draft?.key === key && draft.node === document?.nodeId ? draft.fields : document?.fields;
  const inspected = shown.items.find(item => selection.key === key && item.id === selection.proposal);
  const query = new URLSearchParams({ project, workspace }).toString();

  useEffect(() => {
    const valid = requests.current.next();
    setDraft(null);
    if (!enabled) { setState(empty(key)); return; }
    setState({ ...empty(key), busy: true });
    Promise.all([
      api<PlanContext>(`/api/oporahub/changesets/context?${query}`),
      api<{ items: PlanChangeset[] }>(`/api/oporahub/changesets?${query}`),
      baselineId ? api<{ result: BaselinePreparation }>(`/api/oporahub/baseline-preparations/${encodeURIComponent(baselineId)}?${query}`) : Promise.resolve(undefined),
    ]).then(([context, history, stored]) => {
      if (valid()) {
        setState({ ...empty(key), context, items: history.items, preparation: stored?.result });
        if (changesetId) setSelection({ key, node: "", proposal: changesetId });
      }
    }).catch(error => { if (valid()) setState({ ...empty(key), error: message(error) }); });
    return () => requests.current.invalidate();
  }, [key, enabled, query, attempt, baselineId, changesetId]);

  async function write(path: string, payload: object, applies: boolean) {
    if (shown.busy || writing.current || readOnly || context?.readOnly || !context) return;
    writing.current = true;
    const valid = requests.current.next();
    setState({ ...shown, busy: true, error: "", notice: "" });
    try {
      await api(path, payload);
      // Apply invalidation survives leaving the panel; App guards the captured project/workspace.
      if (applies) onApplied();
      if (!valid()) return;
      // Mutation and follow-up read are separate; never repeat a possibly successful mutation.
      setDraft(null);
      const history = await api<{ items: PlanChangeset[] }>(`/api/oporahub/changesets?${query}`);
      if (valid()) setState({ ...shown, context: null, items: history.items, busy: false, error: "",
        notice: applies ? "Zadání přijato. Obnovte kontext pro další práci. Nejde o ověření implementace." : "Návrh uložen bez změny Canvasu. Obnovte kontext pro další práci." });
    } catch (error) {
      if (valid()) setState({ ...shown, context: null, busy: false, error: message(error) + " Obnovte kontext a zkontrolujte stav před dalším zápisem." });
    } finally { writing.current = false; }
  }

  function baseline() {
    if (!context || context.acceptedHead || !subject.trim() || !preparationMatches) return;
    if (baselineId && preparation) { void write("/api/oporahub/baselines", preparation.payload, true); return; }
    void write("/api/oporahub/baselines", { project, workspace, subject: subject.trim(),
      expectedAcceptedHead: context.acceptedHead, expectedGraphDigest: context.graphDigest,
      expectedSpecificationsVersion: context.specificationsVersion }, true);
  }
  function propose() {
    if (!context || !document || !fields || !subject.trim()) return;
    try { void write("/api/oporahub/changesets", changesetPayload(project, workspace, subject, context, document, fields), false); }
    catch (error) { setState({ ...shown, error: message(error) }); }
  }
  function accept() {
    if (!context?.acceptedHead || !inspected || inspected.accepted) return;
    void write(`/api/oporahub/changesets/${encodeURIComponent(inspected.id)}/accept`,
      { project, workspace, expectedAcceptedHead: context.acceptedHead }, true);
  }
  function rebase() {
    if (!context?.acceptedHead || !inspected || inspected.accepted) return;
    void write(`/api/oporahub/changesets/${encodeURIComponent(inspected.id)}/rebase`,
      { project, workspace, expectedAcceptedHead: context.acceptedHead }, false);
  }
  return { ...shown, documents, document, missingDocument, fields, inspected, subject, baselineId, preparationMatches, readOnly: readOnly || !!context?.readOnly,
    name: (nodeId: string) => nodes.find(node => node.id === nodeId)?.name ?? nodeId,
    setSubject: (text: string) => setTitle({ key, text }),
    selectDocument: (node: string) => { setDraft(null); setSelection({ key, node, proposal: "" }); },
    inspect: (proposal: string) => setSelection({ ...selection, key, proposal }),
    edit: (field: keyof SpecFields, value: string) => {
      if (document && fields) setDraft({ key, node: document.nodeId, fields: { ...fields, [field]: value } });
    },
    refresh: () => { if (!writing.current) { requests.current.invalidate(); setDraft(null); setSelection(previous => refreshedPlanSelection(previous, key)); setAttempt(n => n + 1); } },
    baseline, propose, accept, rebase };
}
export type PlanChangesView = ReturnType<typeof usePlanChanges>;
