import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller } from "@/shared/hooks/logic/poller";
import { REVIEW_ROOT, ReviewRequests, reviewQuery, type ReviewScope, type AcceptancePolicyContext, type AcceptancePolicy } from "./proposal-review";
import { parseAcceptancePolicy } from "./review-parse";
import { postReview } from "./review-api";

export function useAcceptancePolicy(scope: ReviewScope, enabled: boolean, revision: number | string, onChanged: () => void) {
  const [attempt, setAttempt] = useState(0), [pending, setPending] = useState(false);
  const key = JSON.stringify([scope.project, scope.workspace, enabled, revision, attempt]);
  const reads = useRef(new ReviewRequests()), writes = useRef(new ReviewRequests());
  reads.current.context(key); writes.current.context(key);
  const [state, setState] = useState({ key, context: null as AcceptancePolicyContext | null, busy: false, error: "" });
  const shown = state.key === key ? state : { key, context: null, busy: enabled, error: "" };
  useEffect(() => () => writes.current.invalidate(), []);
  useEffect(() => {
    if (!enabled) return;
    const poller = createPoller({ intervalMs: 10000, run: async () => {
      const valid = reads.current.next();
      setState(old => ({ key, context: old.key === key ? old.context : null, busy: true, error: "" }));
      try {
        await api("/api/access/ui-session");
        const context = parseAcceptancePolicy(await api<unknown>(`${REVIEW_ROOT}/policy?${reviewQuery(scope)}`), scope);
        if (valid()) setState({ key, context, busy: false, error: "" });
      } catch (error) { if (valid()) setState({ key, context: null, busy: false, error: error instanceof Error ? error.message : "Pravidla nejsou dostupná." }); }
    } });
    poller.start(); return () => { reads.current.invalidate(); poller.stop(); };
  }, [key]);
  async function configure(value: Pick<AcceptancePolicy, "enabled" | "rules">) {
    if (!shown.context?.canConfigure || shown.busy || pending || !enabled) return;
    const valid = writes.current.begin(); if (!valid) return;
    setPending(true);
    try {
      await postReview(`${REVIEW_ROOT}/policy`, { ...scope, expectedPolicyHead: shown.context.policyHead, ...value });
      onChanged();
      if (valid()) setAttempt(current => current + 1);
    } catch (error) { if (valid()) setState({ key, context: null, busy: false, error: `${error instanceof Error ? error.message : "Zápis odmítnut."} Obnovte pravidla; zápis se automaticky neopakuje.` }); }
    finally { writes.current.end(); setPending(false); }
  }
  return { ...shown, pending, configure, refresh: () => { reads.current.invalidate(); writes.current.invalidate(); setAttempt(v => v + 1); } };
}
export type AcceptancePolicyView = ReturnType<typeof useAcceptancePolicy>;
