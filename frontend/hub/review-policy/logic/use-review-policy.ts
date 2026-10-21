import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { GitEvidenceView } from "@/hub/git-evidence/logic/use-git-evidence";
import { emptyPolicyDraft, policyConfirmation, policyDraft, policyPayload, PolicyRequests, type PolicyContext, type PolicyDraft, type PolicyHistory } from "./review-policy";
import { postPolicy } from "./policy-api";
import { usePolicyStatus } from "./use-policy-status";

const ROOT = "/api/oporahub/review-policy";
const message = (error: unknown) => error instanceof Error ? error.message : String(error);
type State = { key: string; context: PolicyContext | null; history: PolicyHistory["items"]; busy: boolean; error: string; notice: string };
const empty = (key: string): State => ({ key, context: null, history: [], busy: false, error: "", notice: "" });
export function useReviewPolicy(project: string, workspace: string, enabled: boolean, refreshRevision: number, evidence: GitEvidenceView) {
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([project, workspace, enabled, refreshRevision, attempt]);
  const requests = useRef(new PolicyRequests()), active = useRef(key);
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState(() => empty(key)), [writing, setWriting] = useState(false);
  const shown = state.key === key ? state : empty(key);
  const formKey = JSON.stringify([key, shown.context?.policyHead]);
  const [storedDraft, setStoredDraft] = useState({ key: formKey, value: emptyPolicyDraft() });
  const draft = storedDraft.key === formKey ? storedDraft.value : shown.context?.policy ? policyDraft(shown.context.policy) : emptyPolicyDraft();
  const [review, setReview] = useState<{ key: string; action: "activate" | "disable"; payload: object; fingerprint: string } | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const pending = review?.key === formKey ? review : null;
  const disabled = writing || shown.busy || !shown.context?.canConfigure;
  const query = new URLSearchParams({ project, workspace }).toString();
  const evidencePr = evidence.selected?.snapshot.pr?.number ?? evidence.selected?.snapshot.prNumber ?? null;
  const input = evidence.prNumber.trim();
  const prNumber = input ? (/^[1-9][0-9]*$/.test(input) && Number.isSafeInteger(Number(input)) ? Number(input) : null) : evidencePr;
  const statusKey = JSON.stringify([key, evidence.context?.acceptedHead, evidence.items[0]?.snapshot.id, evidence.busy, evidence.failedAttempt]);
  const status = usePolicyStatus(project, workspace, prNumber, enabled && !!shown.context, shown.context?.policyHead ?? null,
    shown.context?.acceptedHead ?? null, statusKey, writing || shown.busy || evidence.busy || evidence.failedAttempt || !evidence.context);

  useEffect(() => {
    const valid = requests.current.next(); setReview(null); setConfirmation("");
    if (!enabled) { setState(empty(key)); return; }
    setState({ ...empty(key), busy: true });
    void (async () => {
      try {
        await api("/api/access/ui-session");
        const [context, history] = await Promise.allSettled([api<PolicyContext>(`${ROOT}?${query}`), api<PolicyHistory>(`${ROOT}/history?${query}`)]);
        if (!valid()) return;
        let current = context.status === "fulfilled" ? context.value : null;
        let error = context.status === "rejected" ? message(context.reason) : "";
        if (history.status === "rejected") error += " " + message(history.reason);
        if (current && history.status === "fulfilled" && current.policyHead !== history.value.policyHead) { current = null; error = "Pravidla se při čtení změnila. Obnovte nastavení."; }
        setState({ ...empty(key), context: current, history: history.status === "fulfilled" ? history.value.items : [], error: error.trim() });
      } catch (error) { if (valid()) setState({ ...empty(key), error: message(error) }); }
    })();
    return () => requests.current.invalidate();
  }, [key, enabled, query]);

  function edit(patch: Partial<PolicyDraft>) { setStoredDraft({ key: formKey, value: { ...draft, ...patch } }); setReview(null); setConfirmation(""); }
  function prepare(action: "activate" | "disable") {
    if (disabled || !shown.context) return;
    try {
      if (action === "disable" && (!shown.context.policyHead || !shown.context.policy?.enabled)) throw new Error("Aktivní pravidla nejsou nastavena.");
      const payload = action === "activate" ? policyPayload(project, workspace, shown.context, draft)
        : { project, workspace, expectedPolicyHead: shown.context.policyHead };
      setReview({ key: formKey, action, payload, fingerprint: policyConfirmation(action, payload) }); setConfirmation("");
      setState({ ...shown, error: "" });
    } catch (error) { setState({ ...shown, error: message(error) }); }
  }
  async function save() {
    if (disabled || !pending || confirmation !== pending.fingerprint) return;
    const valid = requests.current.beginWrite(); if (!valid) return;
    setWriting(true); setConfirmation(""); setState({ ...shown, busy: true, error: "", notice: "" });
    try {
      await postPolicy(`${ROOT}${pending.action === "disable" ? "/disable" : ""}`, pending.payload);
      if (!valid()) return;
      setReview(null); setState({ ...shown, context: null, busy: false, notice: "Nová neměnná revize pravidel byla uložena. Pro její splnění načtěte nové pozorování z GitHubu." });
      evidence.refresh(); setAttempt(value => value + 1);
    } catch (error) {
      if (valid()) { setReview(null); setState({ ...shown, context: null, busy: false, notice: "", error: message(error) + " Obnovte nastavení a historii; zápis se automaticky neopakuje." }); }
    } finally { requests.current.endWrite(); setWriting(false); }
  }
  return { ...shown, busy: shown.busy || writing, disabled, draft, edit, pending, status, evidence,
    confirmed: !!pending && confirmation === pending.fingerprint,
    confirm: (checked: boolean) => setConfirmation(checked && pending ? pending.fingerprint : ""),
    prepare, save, cancel: () => { setReview(null); setConfirmation(""); },
    refresh: () => { if (!requests.current.busy) { requests.current.invalidate(); setReview(null); setConfirmation(""); setAttempt(value => value + 1); } } };
}
export type ReviewPolicyView = ReturnType<typeof useReviewPolicy>;
