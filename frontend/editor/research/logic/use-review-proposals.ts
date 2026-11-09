import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import type { ResearchScope } from "./research-types";
import type { DecisionReview } from "./research-decision";

export type ReviewPreparation = { id: string; digest: string; status: "pending" | "accepted" | "rejected";
  by: { kind: string; name: string }; createdAt: string; snapshot: Omit<DecisionReview, "id" | "reviewedAt">;
  result: DecisionReview | null };
const ROOT = "/api/research/review-proposals";

export function useReviewProposals(scope: ResearchScope, decisionId: string, onReviewed: (value: DecisionReview) => void) {
  const key = JSON.stringify([scope.project, scope.workspace, decisionId]);
  const active = useRef(key), generation = useRef(0);
  if (active.current !== key) { active.current = key; generation.current++; }
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ key, items: [] as ReviewPreparation[], busy: false, error: "" });
  const shown = state.key === key ? state : { key, items: [], busy: true, error: "" };
  const query = new URLSearchParams({ ...scope, decisionId }).toString();
  useEffect(() => {
    const run = ++generation.current;
    setState({ key, items: [], busy: true, error: "" });
    api<{ items: ReviewPreparation[] }>(`${ROOT}?${query}`).then(result => {
      if (generation.current === run) setState({ key, items: result.items, busy: false, error: "" });
    }).catch(error => { if (generation.current === run) setState({ key, items: [], busy: false, error: String(error) }); });
    return () => { generation.current++; };
  }, [key, query, attempt]);
  async function decide(item: ReviewPreparation, action: "accept" | "reject") {
    if (shown.busy || item.status !== "pending") return;
    const run = generation.current;
    setState({ ...shown, busy: true, error: "" });
    try {
      const saved = await api<ReviewPreparation>(`${ROOT}/${encodeURIComponent(item.id)}/${action}`, { ...scope, digest: item.digest });
      if (generation.current !== run) return;
      setState({ ...shown, items: shown.items.map(row => row.id === saved.id ? saved : row), busy: false });
      if (saved.status === "accepted" && saved.result) onReviewed(saved.result);
    } catch (error) { if (generation.current === run) setState({ ...shown, busy: false, error: String(error) }); }
  }
  return { ...shown, decide, refresh: () => { if (!shown.busy) setAttempt(value => value + 1); } };
}
