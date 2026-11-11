import { useSyncExternalStore } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import LiveCard from "@/editor/canvas/live-card/components/LiveCard";
import { cardDrawerStore, closeCardDrawer, openCardDrawer } from "../logic/card-drawer-store";
import type { DrawerEditor } from "../logic/drawer-editor";
import CardDrawer from "./CardDrawer";

const serverSnapshot = () => null;

/**
 * Jediné místo, kde se detail karty vykresluje: App ho připojí jednou nad všemi prostředími (Editor,
 * Velín, OporaHub) a otvírá ho kdokoli přes `openCardDrawer`. Bez záložky ukáže živou kartu na 3/4,
 * se záložkou (nebo po „Pracovní panel“ z karty) drawer se záložkami. Jména karet a ponechané editory dodá App.
 */
export default function CardDrawerHost({ project, workspace, nodes, editor }: {
  project: string; workspace: string; nodes: CanvasNode[]; editor: DrawerEditor | null;
}) {
  const state = useSyncExternalStore(cardDrawerStore.subscribe, cardDrawerStore.get, serverSnapshot);
  if (!state || !project || !workspace) return null;
  const node0 = nodes.find(item => item.id === state.nodeId) ?? null;
  // Vnitřní plátno má sektor, stránka i prvek; obyčejná karta ne (dřív to rozlišoval dvojklik).
  const inner = !!node0 && (node0.kind !== "node" || !!node0.site || !!node0.element);
  const enterCanvas = editor?.onEnterCanvas;
  if (!state.panel) return <LiveCard key={JSON.stringify([project, workspace, state.nodeId])} project={project} workspace={workspace} nodeId={state.nodeId}
    onClose={closeCardDrawer} onPanel={cardDrawerStore.showPanel} onOpenCard={id => openCardDrawer(id)} onAskHeart={editor?.onAskHeart}
    onEnterCanvas={inner && enterCanvas ? () => { closeCardDrawer(); enterCanvas(state.nodeId); } : undefined} />;
  const node = node0;
  const parentName = node?.parentId ? nodes.find(item => item.id === node.parentId)?.name ?? "" : "";
  return <CardDrawer key={JSON.stringify([project, workspace, state.nodeId])} project={project} workspace={workspace} nodeId={state.nodeId}
    tab={state.tab} node={node} parentName={parentName} editor={editor} onTab={cardDrawerStore.setTab} onClose={closeCardDrawer} />;
}
