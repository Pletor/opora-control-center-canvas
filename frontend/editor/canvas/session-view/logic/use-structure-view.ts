import { useMemo, useRef, useState } from "react";
import type { LayerGroupId } from "@/layout/structure-panel/logic/layer-list";
import { observedStructure, togglePrivateGroup, type StructureViewBridge } from "./structure-view";

/** Tab-local overlay only: never writes the user's global Structure preferences. */
export function useStructureView(scope: string) {
  const [value, setValue] = useState<{ scope: string; groups: LayerGroupId[] } | null>(null);
  const activeScope = useRef(scope); activeScope.current = scope;
  const changed = useRef<(() => void) | null>(null);
  const groups = value?.scope === scope ? value.groups : undefined;
  const bridge = useMemo<StructureViewBridge>(() => ({
    apply: groups => { if (activeScope.current === scope) setValue(groups === undefined ? null : { scope, groups }); },
    observed: groups => activeScope.current === scope && observedStructure(groups),
    clear: () => setValue(value => value?.scope === scope ? null : value),
    registerChanged: callback => { changed.current = callback; },
  }), [scope]);
  return { groups, bridge, invalidate: () => { if (groups !== undefined) changed.current?.(); }, toggle: (group: LayerGroupId) => {
    if (groups === undefined) return;
    changed.current?.();
    setValue({ scope, groups: togglePrivateGroup(groups, group) });
  } };
}
