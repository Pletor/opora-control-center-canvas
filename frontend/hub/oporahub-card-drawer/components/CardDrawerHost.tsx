import { useSyncExternalStore } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import { cardDrawerStore, closeCardDrawer } from "../logic/card-drawer-store";
import type { DrawerEditor } from "../logic/drawer-editor";
import CardDrawer from "./CardDrawer";

const serverSnapshot = () => null;

/**
 * Jediné místo, kde se detail karty vykresluje: App ho připojí jednou nad všemi prostředími (Editor,
 * Velín, OporaHub) a otvírá ho kdokoli přes `openCardDrawer`. Jména karet a ponechané editory dodá App.
 */
export default function CardDrawerHost({ project, workspace, nodes, editor }: {
  project: string; workspace: string; nodes: CanvasNode[]; editor: DrawerEditor | null;
}) {
  const state = useSyncExternalStore(cardDrawerStore.subscribe, cardDrawerStore.get, serverSnapshot);
  if (!state || !project || !workspace) return null;
  const node = nodes.find(item => item.id === state.nodeId) ?? null;
  const parentName = node?.parentId ? nodes.find(item => item.id === node.parentId)?.name ?? "" : "";
  return <CardDrawer key={JSON.stringify([project, workspace, state.nodeId])} project={project} workspace={workspace} nodeId={state.nodeId}
    tab={state.tab} node={node} parentName={parentName} editor={editor} onTab={cardDrawerStore.setTab} onClose={closeCardDrawer} />;
}
