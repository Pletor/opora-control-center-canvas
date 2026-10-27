// Převod modelu domény na plátno MODELu: karta podle typu katalogu (ikona, název, typ, rozměr z měřené geometrie),
// porty na obvodu s barvou podle datového typu a stranou podle rozložení vazeb (`layoutStudioConnections` otočí port
// k protějšku), vazby jako Bézierovy křivky barvené typem a uzly React Flow s pevnými rozměry. Během tažení karty
// platí dočasná poloha (`overrides`), aby vazby šly s kartou. Čistá logika bez Reactu.
import type { Node } from "@xyflow/react";
import { componentType, portColor } from "../../model/logic/catalog";
import { cardGeometry } from "../../model/logic/geometry";
import { observedGeometry } from "../../model/logic/observed-geometry";
import { cubicPoint } from "../../model/logic/routing";
import { layoutStudioConnections, type LayoutNode, type PortAnchor, type StudioRoute } from "../../model/logic/studio-routing";
import type { Point, PortDirection, PortSide, PortType } from "../../model/logic/model-types";
import type { EditModel, Selection } from "../../studio-model/logic/model-edit";
import type { BindingCard } from "../../studio-layer/logic/studio-layer";
import type { CardRun } from "../../studio-model-run/logic/run-view";
import { cardStages } from "./card-stages";
import { portKey, type PortTarget } from "./connect-gesture";

export type PortView = { id: string; type: PortType; direction: PortDirection; side: PortSide; x: number; y: number; color: string;
  connected: number; target: PortTarget | null; pending: boolean };
export type BindingBadge = { name: string; state: BindingCard["state"] | "missing"; stateLabel: string };
export type ModelCardView = { id: string; name: string; typeName: string; icon: string; group: string; category: string; provider: string;
  width: number; height: number; ports: PortView[]; stages: readonly string[]; binding: BindingBadge | null; run: CardRun | null };
export type ModelLinkView = { id: string; d: string; color: string; type: PortType; inactive: boolean; selected: boolean; label: string; mid: Point };
export type ModelLayout = { nodes: LayoutNode[]; ports: Map<string, Map<string, PortAnchor>>; routes: Map<string, StudioRoute> };

const FALLBACK = { width: 220, height: 180 };

/** Rozměry karet a trasy vazeb pro aktuální polohy (s dočasnými polohami tažených karet). */
export function modelLayout(model: EditModel, overrides: ReadonlyMap<string, Point> = new Map()): ModelLayout {
  const nodes: LayoutNode[] = model.nodes.map((node) => {
    const position = overrides.get(node.id) ?? node.position, observed = observedGeometry[node.type];
    const size = observed || node.type === "kubernetes-deployment" ? cardGeometry(node) : FALLBACK;
    const ports = (componentType(node.type)?.ports ?? []).map((port) => ({ id: port.id, direction: port.direction, side: observed?.ports.find((o) => o.id === port.id)?.side }));
    return { id: node.id, x: position.x, y: position.y, width: size.width, height: size.height, ports };
  });
  const { ports, routes } = layoutStudioConnections(nodes, model.edges);
  return { nodes, ports, routes };
}

type CardContext = { pending: string | null; targets: ReadonlyMap<string, PortTarget>; bindings: ReadonlyMap<string, BindingCard>; runs?: ReadonlyMap<string, CardRun> };

/** Karty plátna; s během (`runs`) nese karta i vypočtený stav a čísla stupňů (výpočet modelu, ne měření). */
export function modelCards(model: EditModel, layout: ModelLayout, { pending, targets, bindings, runs }: CardContext): ModelCardView[] {
  const connected = new Map<string, number>();
  for (const edge of model.edges) for (const end of [edge.from, edge.to]) connected.set(portKey(end), (connected.get(portKey(end)) ?? 0) + 1);
  return model.nodes.map((node, index) => {
    const type = componentType(node.type), box = layout.nodes[index], anchors = layout.ports.get(node.id);
    const ports: PortView[] = (type?.ports ?? []).map((port) => {
      const anchor = anchors?.get(port.id), key = portKey({ nodeId: node.id, portId: port.id });
      return { id: port.id, type: port.type, direction: port.direction, side: anchor?.side ?? "left", x: anchor?.x ?? 0, y: anchor?.y ?? 0,
        color: portColor(port.type, port.direction), connected: connected.get(key) ?? 0, target: targets.get(key) ?? null, pending: pending === key };
    });
    const bound = node.binding ? bindings.get(node.binding.nodeId) : undefined;
    const binding: BindingBadge | null = !node.binding ? null : bound ? { name: bound.name, state: bound.state, stateLabel: bound.stateLabel }
      : { name: node.binding.nodeId, state: "missing", stateLabel: "karta chybí" };
    return { id: node.id, name: node.name, typeName: type?.name ?? node.type, icon: type?.icon ?? "□", group: type?.group ?? "", category: type?.category ?? "",
      provider: type?.provider ?? "", width: box.width, height: box.height, ports, stages: cardStages(node.type), binding, run: runs?.get(node.id) ?? null };
  });
}

export function modelLinks(model: EditModel, layout: ModelLayout, selection: Selection): ModelLinkView[] {
  return model.edges.flatMap((edge) => {
    const route = layout.routes.get(edge.id);
    if (!route) return [];
    const [p, a, b, q] = route.points;
    return [{ id: edge.id, d: route.d, color: portColor(edge.type), type: edge.type, inactive: !edge.enabled, label: edge.label ?? "",
      selected: selection?.kind === "edge" && selection.id === edge.id, mid: cubicPoint(p, a, b, q, 0.5) }];
  });
}

export type ModelCardNode = Node<{ card: ModelCardView }, "model-card">;

/** Uzly React Flow s pevnými rozměry (plátno je řízené, změřené rozměry se nevrací) a vybranou kartou. */
export function modelFlowNodes(cards: ModelCardView[], layout: ModelLayout, selection: Selection): ModelCardNode[] {
  return cards.map((card, index) => ({
    id: card.id, type: "model-card", position: { x: layout.nodes[index].x, y: layout.nodes[index].y }, width: card.width, height: card.height,
    data: { card }, selected: selection?.kind === "node" && selection.id === card.id, connectable: false,
  }));
}
