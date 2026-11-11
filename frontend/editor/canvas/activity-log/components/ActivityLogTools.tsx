// Ikonka Záznam činnosti v horní liště a pod ní panel. Rodič dílků: drží otevřenost, záložku
// (Já / Agenti) a filtr „jen vybraná karta“ a přes `useActivityLog` čte záznam jen při otevřeném
// panelu. Rozsah (projekt, prostor), karty plátna, výběr a otevření karty dostává od App.
import { useCallback, useState } from "react";
import ActivityLogButton from "@/editor/canvas/activity-log/components/ActivityLogButton";
import ActivityLogPanel from "@/editor/canvas/activity-log/components/ActivityLogPanel";
import { useActivityLog } from "@/editor/canvas/activity-log/logic/use-activity-log";
import type { Actor } from "@/editor/canvas/activity-log/logic/activity-log";
import "@/editor/canvas/activity-log/styles/activity-log.css";

export default function ActivityLogTools({ project, workspace, nodes, selectedNodeId, refreshKey, onOpenNode }: {
  project: string;
  workspace: string;
  /** Karty plátna pro jména; karta mimo graf zůstane ID. */
  nodes: { id: string; name: string }[];
  selectedNodeId: string | null;
  /** Otisk plátna a revize: změna = načíst nové zápisy. */
  refreshKey: string;
  onOpenNode: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Actor>("human");
  const [onlySelected, setOnlySelected] = useState(false);
  const nodeId = onlySelected && selectedNodeId ? selectedNodeId : null;
  const log = useActivityLog({ project, workspace, nodeId, enabled: open, refreshKey });
  const close = useCallback(() => setOpen(false), []);
  const selectedName = selectedNodeId ? nodes.find((node) => node.id === selectedNodeId)?.name ?? selectedNodeId : null;
  return (
    <div className="activity-log" role="group" aria-label="Záznam činnosti">
      <ActivityLogButton open={open} onToggle={() => setOpen((value) => !value)} />
      {open && (
        <ActivityLogPanel tab={tab} log={log} nodes={nodes} selectedName={selectedName} onlySelected={!!nodeId}
          onTab={setTab} onToggleSelected={() => setOnlySelected((value) => !value)}
          onLoadOlder={() => log.loadOlder(tab)} onOpenNode={onOpenNode} onClose={close} />
      )}
    </div>
  );
}
