import { useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";
import { proposeStoryboard, storyboardReviewLink } from "./storyboard-proposal";

export function useStoryboardProposal(project: string, workspace: string, nodeId: string, revision: number) {
  const key = JSON.stringify([project, workspace, nodeId, revision]);
  const current = useRef(key); current.current = key;
  const [state, setState] = useState({ key: "", busy: false, error: "", href: "" });
  const shown = state.key === key ? state : { busy: false, error: "", href: "" };
  const pending = useRef(false);
  async function propose() {
    if (pending.current) return;
    pending.current = true;
    setState({ key, busy: true, error: "", href: "" });
    try {
      const proposal = await proposeStoryboard({ project, workspace }, nodeId, revision, api);
      if (current.current === key) setState({ key, busy: false, error: "", href: storyboardReviewLink({ project, workspace }, proposal.id) });
    } catch (error) {
      if (current.current === key) setState({ key, busy: false, href: "", error: error instanceof Error ? error.message : String(error) });
    } finally { pending.current = false; }
  }
  return { ...shown, propose };
}
