import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/shared/types/logic/types";
import type { ResearchScope } from "./research-types";
import type { DecisionReview, ResearchTask, TaskProposal } from "./research-decision";

export function useResearchDecision(scope: ResearchScope, decisionId: string) {
  const [reviews, setReviews] = useState<DecisionReview[]>([]);
  const [selected, setSelected] = useState("");
  const [proposal, setProposal] = useState<TaskProposal | null>(null);
  const [busy, setBusy] = useState(true); const [error, setError] = useState("");
  const generation = useRef(0);
  const query = new URLSearchParams(scope).toString();
  const loadProposal = async (id: string) => {
    try { return await api<TaskProposal>(`/api/research/decision-reviews/${encodeURIComponent(id)}/tasks?${query}`); }
    catch (reason) { if (reason instanceof ApiError && reason.status === 404) return null; throw reason; }
  };
  useEffect(() => {
    const ticket = ++generation.current;
    setReviews([]); setSelected(""); setProposal(null); setBusy(true); setError("");
    api<{ reviews: DecisionReview[] }>(`/api/research/decision-reviews?${query}&decisionId=${encodeURIComponent(decisionId)}`)
      .then(async result => {
        const latest = result.reviews.at(-1); const receipt = latest ? await loadProposal(latest.id) : null;
        if (generation.current === ticket) { setReviews(result.reviews); setSelected(latest?.id ?? ""); setProposal(receipt); }
      }).catch(reason => { if (generation.current === ticket) setError(String(reason)); })
      .finally(() => { if (generation.current === ticket) setBusy(false); });
    return () => { generation.current++; };
  }, [query, decisionId]);
  const run = async (work: (active: () => boolean) => Promise<void>) => {
    const ticket = generation.current;
    const active = () => generation.current === ticket;
    setBusy(true); setError("");
    try { await work(active); } catch (reason) { if (active()) setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { if (active()) setBusy(false); }
  };
  const select = (id: string) => run(async active => { setSelected(id); const receipt = id ? await loadProposal(id) : null; if (active()) setProposal(receipt); });
  const review = (body: object) => run(async active => {
    const value = await api<DecisionReview>("/api/research/decision-reviews", { ...scope, review: body });
    if (active()) { setReviews(current => [...current.filter(item => item.id !== value.id), value]); setSelected(value.id); setProposal(null); }
  });
  const propose = (tasks: ResearchTask[]) => run(async active => {
    const receipt = await api<TaskProposal>(`/api/research/decision-reviews/${encodeURIComponent(selected)}/tasks`, { ...scope, tasks });
    if (active()) setProposal(receipt);
  });
  const reconcile = () => run(async active => {
    const receipt = await api<TaskProposal>(`/api/research/decision-reviews/${encodeURIComponent(selected)}/reconcile`, scope);
    if (active()) setProposal(receipt);
  });
  const refresh = () => select(selected);
  return { reviews, selected, proposal, busy, error, select, review, propose, refresh, reconcile };
}
