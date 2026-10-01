// Plocha záložky Agenti přes celou šířku: vlevo lišta karet vrstvy, vpravo segmenty vybrané karty.
// Deska drží dvě věci, které dílky samy držet nesmějí: kterou kartu člověk vybral a co je rozbalené.
// Rozbalení je vzhled, ne obsah, proto se ukládá jednou pro celou aplikaci (`opora:agent-segments:v1`),
// nikdy s klíčem projektu. Napravo je vždy právě jeden `AgentWorkspace` s `key={nodeId}` — zbylé
// karty se nenačítají, dokud na ně člověk neklikne, takže vrstva s deseti dětmi nedělá deset dotazů.
import { useMemo, useState } from "react";
import AgentWorkspace from "@/editor/node-detail/agent-workspace/components/AgentWorkspace";
import { agentRoleOf, setAgentRole } from "@/editor/node-detail/agent-workspace/memory/logic/agent-role";
import AgentCardRail, { type RailCard } from "@/editor/node-detail/agent-workspace/segments/components/AgentCardRail";
import {
  collapseAll,
  defaultOpen,
  expandAll,
  mergeOpen,
  readSegmentPrefs,
  writeSegmentPrefs,
  type SegmentId,
  type SegmentOpen,
  type SegmentStorage,
} from "@/editor/node-detail/agent-workspace/segments/logic/agent-segments";
import type { SectionKey } from "@/editor/node-detail/agent-workspace/logic/agent-workspace";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import type { CanvasNode } from "@/shared/types/logic/types";
import "@/editor/node-detail/agent-workspace/segments/styles/agent-segments.css";

const KIND_LABEL: Record<CanvasNode["kind"], string> = {
  sector: "Sektor", node: "Uzel", comment: "Poznámka", area: "Oblast",
};

/** Úložiště prohlížeče, nebo nic: v soukromém okně i v testu se čtení jen tiše vzdá. */
function browserStorage(): SegmentStorage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

export default function AgentSegmentsBoard({
  project,
  workspace,
  layer,
  children,
  isClosed,
  onEnter,
}: {
  project: string;
  workspace: string;
  layer?: CanvasNode;
  children: CanvasNode[];
  /** Uzavřená karta (done.confirmed) nedovolí zápis; rozhoduje o tom rodič stránky, ne deska. */
  isClosed: (nodeId: string) => boolean;
  onEnter: (id: string) => void;
}) {
  const storage = useMemo(browserStorage, []);
  const cards = useMemo<RailCard[]>(() => [
    ...(layer ? [{ id: layer.id, name: layer.name, kindLabel: "Vrstva", enterable: false }] : []),
    ...children.map((node) => ({
      id: node.id, name: node.name, kindLabel: KIND_LABEL[node.kind], enterable: true,
    })),
  ], [layer, children]);
  // Role karty je pole uzlu ve stavu Desktop v3, ne nastavení panelu: drží ji tedy deska, která
  // jediná má revizi a zámek zápisu, a dílcům ji rozdává v props. Žádná nová cesta ukládání.
  const desktop = useDesktopState(project, workspace);
  const [picked, setPicked] = useState("");
  // Vybraná karta žije jen tak dlouho, dokud je na ploše: po přechodu na jinou vrstvu padá výběr
  // zpátky na vrstvu samotnou, aby vpravo nikdy nestála karta, která už v liště není.
  const selected = cards.some((card) => card.id === picked) ? picked : cards[0]?.id ?? "";
  const [open, setOpen] = useState<SegmentOpen>(() => mergeOpen(defaultOpen(), readSegmentPrefs(storage)));

  function remember(next: SegmentOpen) {
    setOpen(next);
    writeSegmentPrefs(storage, { open: next });
  }

  // Pole paměti se poprvé otevřou podle toho, co karta nese; uložená preference člověka má přednost,
  // proto se čte znovu právě teď — mezitím už mohl něčím pohnout.
  function seedFromCard(memory: Record<SectionKey, boolean>) {
    setOpen(mergeOpen(defaultOpen(memory), readSegmentPrefs(storage)));
  }

  function goTo(id: SegmentId) {
    if (!open[id]) remember({ ...open, [id]: true });
  }

  if (!selected) {
    return (
      <p className="muted">
        Tato vrstva nemá kartu, ke které by šel vést pracovní prostor agenta. Přidejte uzel nebo sektor.
      </p>
    );
  }

  return (
    <div className="agent-segments" data-testid="agent-segments">
      <AgentCardRail cards={cards} selected={selected} onSelect={setPicked} onEnter={onEnter} />
      <div className="agent-segments__grid">
        <AgentWorkspace
          key={selected}
          project={project}
          workspace={workspace}
          nodeId={selected}
          readOnly={isClosed(selected)}
          layout="segments"
          open={open}
          onToggle={(id, isOpen) => remember({ ...open, [id]: isOpen })}
          onGoTo={goTo}
          onExpandAll={() => remember(expandAll())}
          onCollapseAll={() => remember(collapseAll())}
          onMemoryDefaults={seedFromCard}
          agentRole={agentRoleOf(desktop.state, selected)}
          onRoleChange={desktop.readOnly ? undefined : (role) => void desktop.mutate(setAgentRole(selected, role))}
        />
      </div>
    </div>
  );
}
