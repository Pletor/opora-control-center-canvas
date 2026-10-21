import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller } from "@/shared/hooks/logic/poller";
import type { GitEvidenceView } from "@/hub/git-evidence/logic/use-git-evidence";
import { controlPayload, enrollmentPayload, ReconciliationIntents, ReconciliationRequests, ROOT, type ControlAction, type ReconciliationContext } from "./reconciliation";
import { postReconciliation } from "./reconciliation-api";
import { useReconciliationCandidate, useReconciliationHistory } from "./use-reconciliation-reads";

const message = (error: unknown) => error instanceof Error ? error.message : String(error);
type Pending = { key: string; action: "enroll" | ControlAction; path: string; payload: object; fingerprint: string };
export function useGithubReconciliation(project: string, workspace: string, enabled: boolean, refreshRevision: number, evidence: GitEvidenceView) {
  const scope = JSON.stringify([project, workspace]);
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([scope, enabled, refreshRevision, attempt]);
  const requests = useRef(new ReconciliationRequests()), active = useRef(key), intents = useRef(new ReconciliationIntents());
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState<{ key: string; context: ReconciliationContext | null; busy: boolean; error: string }>({ key, context: null, busy: false, error: "" });
  const [writing, setWriting] = useState(false), [pending, setPending] = useState<Pending | null>(null), [ack, setAck] = useState("");
  const shown = state.key === key ? state : { key, context: null, busy: false, error: "" };
  const [selection, setSelection] = useState({ scope, id: "" }), [source, setSource] = useState({ scope, id: "" });
  const evidenceId = source.scope === scope ? source.id : "";
  const items = shown.context?.items ?? [];
  const selected = items.find(item => selection.scope === scope && item.binding.id === selection.id) ?? items[0] ?? null;
  const candidateRevision = JSON.stringify([key, shown.context?.currentAcceptedHead, items.map(item => [item.binding.id, item.control.generation])]);
  const candidate = useReconciliationCandidate(project, workspace, evidenceId, enabled && !!shown.context, candidateRevision);
  const history = useReconciliationHistory(project, workspace, selected?.binding.id ?? "", enabled, key);
  const confirmationKey = JSON.stringify([key, selected?.binding.id, selected?.control.generation, evidenceId, candidateRevision]);
  const review = pending?.key === confirmationKey ? pending : null;
  const disabled = writing || shown.busy || !!shown.error || !shown.context?.canConfigure;
  const pauseAllowed = !writing && !shown.busy && !shown.error && !!shown.context?.canPause;
  useEffect(() => {
    if (!enabled) return;
    const read = async () => {
      if (requests.current.busy) return;
      const valid = requests.current.next();
      setState(previous => ({ key, context: previous.key === key ? previous.context : null, busy: true, error: "" }));
      try {
        await api("/api/access/ui-session");
        const context = await api<ReconciliationContext>(`${ROOT}?${new URLSearchParams({ project, workspace })}`);
        if (valid()) setState({ key, context, busy: false, error: "" });
      } catch (error) { if (valid()) setState(previous => ({ ...previous, key, busy: false, error: message(error) })); }
    };
    const poller = createPoller({ run: read, intervalMs: 15000 }); poller.start();
    return () => { requests.current.invalidate(); poller.stop(); };
  }, [key, project, workspace, enabled]);
  function prepare(action: "enroll" | ControlAction) {
    if ((action === "pause" ? !pauseAllowed : disabled) || !shown.context) return;
    try {
      let base: object, path: string;
      if (action === "enroll") {
        if (candidate.busy || !candidate.candidate) throw new Error("Nejprve načtěte serverový přehled zvoleného pozorování.");
        base = enrollmentPayload(project, workspace, shown.context, candidate.candidate); path = `${ROOT}/bindings`;
      } else {
        if (!selected) throw new Error("Vyberte existující vazbu.");
        base = controlPayload(project, workspace, selected, action); path = `${ROOT}/${encodeURIComponent(selected.binding.id)}/control`;
      }
      const payload = { ...base, requestId: intents.current.request(`${action}:${path}`, base) };
      setPending({ key: confirmationKey, action, path, payload, fingerprint: JSON.stringify([path, payload]) }); setAck("");
    } catch (error) { setState({ ...shown, error: message(error) }); }
  }
  async function save() {
    if (!review || (review.action === "pause" ? !pauseAllowed : disabled) || ack !== review.fingerprint) return;
    const valid = requests.current.beginWrite(); if (!valid) return;
    setWriting(true); setAck("");
    try {
      const result = await postReconciliation<{ binding: { id: string } }>(review.path, review.payload);
      if (!valid()) return;
      setPending(null); setSelection({ scope, id: result.binding.id }); setAttempt(value => value + 1);
    } catch (error) {
      if (valid()) { setPending(null); setState({ ...shown, error: message(error) + " Obnovte historii a stav před dalším výslovným pokusem. Zápis se automaticky neopakuje." }); }
    } finally { requests.current.endWrite(); setWriting(false); }
  }
  return { ...shown, busy: shown.busy || writing, items, selected, candidate, history, evidence, evidenceId, review, disabled, pauseAllowed,
    confirmed: !!review && ack === review.fingerprint,
    select: (id: string) => { if (!writing) { setPending(null); setAck(""); setSelection({ scope, id }); } },
    selectEvidence: (id: string) => { if (!writing) { setPending(null); setAck(""); setSource({ scope, id }); } },
    prepare, save, confirm: (value: boolean) => setAck(value && review ? review.fingerprint : ""),
    cancel: () => { setPending(null); setAck(""); },
    refresh: () => { if (!requests.current.busy) { requests.current.invalidate(); setPending(null); setAck(""); setAttempt(value => value + 1); } } };
}
export type GithubReconciliationView = ReturnType<typeof useGithubReconciliation>;
