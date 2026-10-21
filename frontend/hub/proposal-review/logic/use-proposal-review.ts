import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { createPoller } from "@/shared/hooks/logic/poller";
import { REVIEW_ROOT, ReviewRequests, reviewQuery, type ReviewContext, type ReviewScope, type ReviewTarget } from "./proposal-review";
import { parseReview, parseReviewEvent } from "./review-parse";
import { postReview } from "./review-api";

const message = (error: unknown) => error instanceof Error ? error.message : "Review není dostupné.";
export function useProposalReview(scope: ReviewScope, target: ReviewTarget, enabled: boolean, revision: number | string, onChanged: () => void) {
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([scope.project, scope.workspace, target.proposalKind, target.proposalId, enabled, revision, attempt]);
  const reads = useRef(new ReviewRequests()), writes = useRef(new ReviewRequests());
  reads.current.context(key); writes.current.context(key);
  const [state, setState] = useState({ key, context: null as ReviewContext | null, busy: false, error: "" });
  const [pending, setPending] = useState(false), [failure, setFailure] = useState({ key, error: "" });
  const shown = state.key === key ? state : { key, context: null, busy: enabled && !!target.proposalId, error: "" };
  useEffect(() => () => writes.current.invalidate(), []);
  useEffect(() => {
    if (!enabled || !target.proposalId) return;
    const poller = createPoller({ intervalMs: 10000, run: async () => {
      const valid = reads.current.next();
      setState(old => ({ key, context: old.key === key ? old.context : null, busy: true, error: "" }));
      try {
        await api("/api/access/ui-session");
        const context = parseReview(await api<unknown>(`${REVIEW_ROOT}?${reviewQuery(scope, target)}`), scope, target);
        if (valid()) setState({ key, context, busy: false, error: "" });
      } catch (error) { if (valid()) setState({ key, context: null, busy: false, error: message(error) }); }
    } });
    poller.start(); return () => { reads.current.invalidate(); poller.stop(); };
  }, [key]);
  async function write(body: Record<string, unknown>) {
    const context = shown.context;
    if (!enabled || !context || context.readOnly || pending || shown.busy || shown.error) return;
    if ((body.type === "ack" && !context.canAcknowledge) || (body.type === "resolve" && !context.canResolve)) return;
    const valid = writes.current.begin(); if (!valid) return;
    const payload = { ...scope, ...target, expectedReviewHead: context.reviewHead, idempotencyKey: crypto.randomUUID(), body };
    setPending(true); setFailure({ key, error: "" });
    try {
      const result = parseReviewEvent(await postReview(`${REVIEW_ROOT}/events`, payload), scope, target);
      if (result.parentReviewEvent !== context.reviewHead) throw new Error("Server vrátil jinou hlavu review.");
      onChanged();
      if (valid()) { reads.current.invalidate(); setAttempt(value => value + 1); }
    } catch (error) {
      if (valid()) { setState({ key, context: null, busy: false, error: "" }); setFailure({ key, error: message(error) + " Akce se automaticky neopakuje. Obnovte review a zkontrolujte historii." }); }
    } finally { writes.current.end(); setPending(false); }
  }
  return { ...shown, ...scope, pending, target, actionError: failure.key === key ? failure.error : "",
    refresh: () => { reads.current.invalidate(); writes.current.invalidate(); setAttempt(value => value + 1); },
    write, reset: () => { writes.current.invalidate(); reads.current.invalidate(); setAttempt(value => value + 1); } };
}
export type ProposalReviewView = ReturnType<typeof useProposalReview>;
