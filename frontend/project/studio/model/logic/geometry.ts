// Geometrie karet MODELU (prototyp `geometry.mjs`, profil `studio-observed/1`): změřený rozměr karty podle typu,
// poloha portu na obvodu, rozměr Kubernetes Deployment s Pody uvnitř a podklad rodin typů (`architectureAreas`).
// Jen odvozené zobrazení: nic z toho nemění definici modelu ani výpočet simulace.
import { observedArchitecture, observedGeometry, type ArchitectureGroup } from "./observed-geometry";
import type { Point, PortSide, StudioModel, StudioModelNode } from "./model-types";

export const STUDIO_GEOMETRY = "studio-observed/1";
export const CONTROLLER_TYPE = "kubernetes-deployment";

export type Size = { width: number; height: number };
export type ControllerGeometry = Size & { podWidth: number; podHeight: number; left: number; top: number; column: number; row: number };
/** Pod řízený Deploymentem; `viewOffset` je jen prezentační posun ručně přidaného Podu, ne vstup modelu. */
export type PodInstance = { id: string; viewOffset?: { profile: string; x: number; y: number } };
export type ControllerState = { instances: PodInstance[] };

export function ownedPodPosition(index: number, g: ControllerGeometry, pod?: PodInstance): Point {
  const v = pod?.viewOffset;
  return v?.profile === STUDIO_GEOMETRY && Number.isFinite(v.x) && Number.isFinite(v.y)
    ? { x: v.x, y: v.y } : { x: g.left + (index % 2) * g.column, y: g.top + Math.floor(index / 2) * g.row };
}

/** Deployment roste po řadách dvou Podů; ručně posunutý Pod kartu prodlouží. */
export function controllerGeometry(count = 2, instances: readonly PodInstance[] = []): ControllerGeometry {
  const rows = Math.max(1, Math.ceil(count / 2));
  const g = { width: 518, height: 309 + (rows - 1) * 174, podWidth: 220, podHeight: 158, left: 20, top: 131, column: 246, row: 174 };
  instances.forEach((pod, index) => { g.height = Math.max(g.height, ownedPodPosition(index, g, pod).y + g.podHeight + 20); });
  return g;
}

/** Ručně přidané Pody dostanou prezentační posun v dalším řádku; ostatní zůstávají. Vstup se nemění. */
export function withManualPodView(controller: ControllerState, previous?: ControllerState): ControllerState {
  const s = structuredClone(controller), ids = new Set((previous?.instances ?? []).map((p) => p.id)), g = controllerGeometry(s.instances.length);
  s.instances.forEach((pod, index) => {
    if (!ids.has(pod.id)) pod.viewOffset = { profile: STUDIO_GEOMETRY, x: g.left + (index % 2) * g.column, y: g.top + Math.floor(index / 2) * (g.row + 2) };
  });
  return s;
}

type CardOptions = { model?: boolean; count?: number; instances?: readonly PodInstance[] };

/** Rozměr karty: ve Skutečnosti (`model: false`) jednotná karta 270×230, v MODELU změřený rozměr typu. */
export function cardGeometry(node: Pick<StudioModelNode, "type">, { model = true, count = 2, instances = [] }: CardOptions = {}): Size | ControllerGeometry {
  if (!model) return { width: 270, height: 230 };
  if (node.type === CONTROLLER_TYPE) return controllerGeometry(count, instances);
  const shape = observedGeometry[node.type];
  if (!shape) throw new Error("Missing observed geometry " + node.type);
  return { width: shape.width, height: shape.height };
}

/** Kotva portu v souřadnicích karty: strana a poměr z měření, na libovolném rozměru karty. */
export function observedPortPosition(type: string, portId: string, size: Size): Point & { side: PortSide } {
  const anchor = observedGeometry[type]?.ports.find((p) => p.id === portId);
  if (!anchor) throw new Error("Missing observed port anchor " + type + "." + portId);
  const { side, fraction } = anchor;
  return { side, x: side === "left" ? 0 : side === "right" ? size.width : size.width * fraction, y: side === "top" ? 0 : side === "bottom" ? size.height : size.height * fraction };
}

export type ArchitectureArea = ArchitectureGroup & { members: string[]; left: number; top: number; width: number; height: number };

/** Podklad rodin typů (vstup, brány, výpočet, data…) jako obálka karet a Podů s okraji; jen v MODELU. */
export function architectureAreas(model: Pick<StudioModel, "nodes">, { model: isModel = true, controllers = {} }: { model?: boolean; controllers?: Record<string, ControllerState> } = {}): ArchitectureArea[] {
  if (!isModel) return [];
  type Acc = ArchitectureGroup & { members: string[]; left: number; top: number; right: number; bottom: number };
  const groups = new Map<string, Acc>(), padding = observedArchitecture.padding;
  const add = (id: string, type: string, x: number, y: number, width: number, height: number) => {
    const groupId = observedArchitecture.types[type], spec = groupId ? observedArchitecture.groups[groupId] : undefined;
    if (!spec) throw new Error("Missing source family assignment " + type);
    const group = groups.get(spec.id) ?? { ...spec, members: [], left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity };
    group.members.push(id);
    group.left = Math.min(group.left, x); group.top = Math.min(group.top, y);
    group.right = Math.max(group.right, x + width); group.bottom = Math.max(group.bottom, y + height);
    groups.set(spec.id, group);
  };
  for (const node of model.nodes) {
    const instances = controllers[node.id]?.instances ?? [], g = cardGeometry(node, { count: instances.length || 2, instances });
    add(node.id, node.type, node.position.x, node.position.y, g.width, g.height);
    if (node.type === CONTROLLER_TYPE) instances.forEach((pod, index) => {
      const c = g as ControllerGeometry, p = ownedPodPosition(index, c, pod);
      add(pod.id, "pod", node.position.x + p.x, node.position.y + p.y, c.podWidth, c.podHeight);
    });
  }
  return [...groups.values()].map(({ right, bottom, ...g }) => ({ ...g, left: g.left - padding.left, top: g.top - padding.top,
    width: right - g.left + padding.left + padding.right, height: bottom - g.top + padding.top + padding.bottom }));
}
