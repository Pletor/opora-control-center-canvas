import type { LayerGroupId } from "@/layout/structure-panel/logic/layer-list";

export type StructureViewBridge = {
  apply: (groups: LayerGroupId[] | undefined) => void;
  observed: (groups: LayerGroupId[] | undefined) => boolean;
  clear: () => void;
  registerChanged: (changed: (() => void) | null) => void;
};
export const STRUCTURE_GROUPS: LayerGroupId[] = ["sectors", "nodes", "areas"];

/** A hidden or absent tree is not proof that the user sees the requested state. */
export function observedStructure(groups: LayerGroupId[] | undefined, root: ParentNode = document): boolean {
  if (groups === undefined) return true;
  return STRUCTURE_GROUPS.every(group => {
    const element = root.querySelector<HTMLElement>(`[data-testid="structure-group-${group}"]`);
    return !!element && element.getClientRects().length > 0
      && getComputedStyle(element).visibility !== "hidden"
      && element.getAttribute("aria-expanded") === String(!groups.includes(group));
  });
}

export function togglePrivateGroup(groups: LayerGroupId[], group: LayerGroupId): LayerGroupId[] {
  return groups.includes(group) ? groups.filter(item => item !== group) : [...groups, group];
}
