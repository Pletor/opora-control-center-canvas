import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller } from "@/shared/hooks/logic/poller";
import { policyDeadline, PolicyRequests, visiblePolicyStatus, type PolicyEvaluation } from "./review-policy";

export function usePolicyStatus(project: string, workspace: string, prNumber: number | null, enabled: boolean,
  policyHead: string | null, acceptedHead: string | null, revisionKey: string, invalidated: boolean) {
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([project, workspace, prNumber, enabled, policyHead, acceptedHead, revisionKey, invalidated, attempt]);
  const active = useRef(key), requests = useRef(new PolicyRequests());
  if (active.current !== key) { active.current = key; requests.current.invalidate(); }
  const [state, setState] = useState<{ key: string; value: PolicyEvaluation | null; deadline: number; busy: boolean; error: string }>(
    { key, value: null, deadline: 0, busy: false, error: "" });
  const [clock, setClock] = useState(() => performance.now());
  const shown = state.key === key ? state : { key, value: null, deadline: 0, busy: false, error: "" };
  useEffect(() => {
    if (!shown.value?.freshness.expiresAt || shown.deadline <= 0) return;
    const timer = setTimeout(() => setClock(performance.now()), Math.max(0, shown.deadline - performance.now()) + 1);
    return () => clearTimeout(timer);
  }, [shown.deadline, shown.value]);
  useEffect(() => {
    if (!enabled || !prNumber || invalidated) return;
    let pending = false;
    const read = async () => {
      if (pending) return;
      pending = true;
      const valid = requests.current.next(), startedAt = performance.now();
      setState({ key, value: null, deadline: 0, busy: true, error: "" });
      try {
        const query = new URLSearchParams({ project, workspace, prNumber: String(prNumber) });
        const result = await api<{ policyEvaluation: PolicyEvaluation }>(`/api/oporahub/review-policy/status?${query}`);
        if (!valid()) return;
        const value = result.policyEvaluation;
        if (value.status === "satisfied" && (value.policyRevision !== policyHead || value.binding.acceptedRevision !== acceptedHead))
          throw new Error("Pravidla nebo přijatá revize se během čtení změnily. Obnovte nastavení.");
        const received = performance.now();
        setClock(received); setState({ key, value, deadline: policyDeadline(value, startedAt, received), busy: false, error: "" });
      } catch (error) {
        if (valid()) setState({ key, value: null, deadline: 0, busy: false, error: error instanceof Error ? error.message : String(error) });
      } finally { pending = false; }
    };
    // Re-evaluate stored evidence only. Never launch a GitHub observation automatically.
    const polling = createPoller({ run: read, intervalMs: 15000 });
    polling.start();
    const ticking = setInterval(() => setClock(performance.now()), 250);
    return () => { requests.current.invalidate(); polling.stop(); clearInterval(ticking); };
  }, [key, project, workspace, prNumber, enabled, invalidated, policyHead, acceptedHead]);
  return { ...shown, status: visiblePolicyStatus(shown.value, shown.deadline, Math.max(clock, performance.now()), invalidated || shown.busy),
    prNumber, invalidated, refresh: () => { requests.current.invalidate(); setAttempt(value => value + 1); } };
}
export type PolicyStatusView = ReturnType<typeof usePolicyStatus>;
