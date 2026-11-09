import { useMemo, useRef, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { readIntake } from "@/editor/control-tower/intake-plan/logic/intake-api";
import type { IntakeResponse } from "@/editor/control-tower/intake-plan/logic/intake-plan";
import { activeMilestones, milestoneMembers } from "./milestone-focus";

export function useMilestoneFocus(context: { project: string; workspace: string } | undefined, graph: Graph, refresh: string) {
  const project = context?.project ?? "", workspace = context?.workspace ?? "";
  const scope = `${project}\n${workspace}`;
  const current = useRef(scope); current.current = scope;
  const [read, setRead] = useState<{ scope: string; data: IntakeResponse | null; error: string | null } | null>(null);
  const [selection, setSelection] = useState<{ scope: string; id: string } | null>(null);
  usePolling(async () => {
    try {
      const data = await readIntake(project, workspace);
      if (current.current === scope) setRead({ scope, data, error: null });
    } catch (error) {
      if (current.current === scope) setRead(previous => ({ scope, data: previous?.scope === scope ? previous.data : null,
        error: error instanceof Error ? error.message : "Milníky se nepodařilo načíst." }));
    }
  }, { enabled: !!project && !!workspace, intervalMs: 30_000, refreshKeys: [scope], debouncedKeys: [refresh] });
  const snapshot = read?.scope === scope ? read : null;
  const choices = useMemo(() => activeMilestones(snapshot?.data ?? null), [snapshot?.data]);
  // The first active result is visible by default. Explicit 'all' remains a local view preference.
  const selected = selection?.scope === scope ? selection.id : choices[0]?.id ?? "";
  const milestone = choices.find(item => item.id === selected) ?? null;
  const members = useMemo(() => milestone ? milestoneMembers(graph, milestone.cards) : null, [graph, milestone]);
  return { choices, milestone, members, selected: milestone?.id ?? "", error: snapshot?.error ?? null,
    loading: !!context && !snapshot, select: (id: string) => setSelection({ scope, id }) };
}
