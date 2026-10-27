// Zanoření a výběr Studia: zanoření žije v adrese (`studioFocus`, docs/studio.md §2), výběr jen v paměti a po změně
// úrovně se zruší. Neznámé id z adresy se po načtení grafu bere jako úroveň projektu a adresa se srovná.
import { useCallback, useEffect, useState } from "react";
import { readStudioFocus, STUDIO_FOCUS_PARAM, withStudioFocus } from "./studio-route";
import type { StudioTree } from "./studio-tree";

export function useStudioFocus(tree: StudioTree, loaded: boolean) {
  const [wanted, setWanted] = useState<string | null>(() => new URLSearchParams(location.search).get(STUDIO_FOCUS_PARAM));
  const [selected, setSelected] = useState<string | null>(null);
  const focus = loaded ? readStudioFocus(new URLSearchParams(wanted ? { [STUDIO_FOCUS_PARAM]: wanted } : {}), tree) : null;
  useEffect(() => {
    if (!loaded) return;
    const next = withStudioFocus(new URLSearchParams(location.search), focus);
    if (next.toString() !== new URLSearchParams(location.search).toString()) history.replaceState(null, "", "/?" + next);
  }, [loaded, focus]);
  const open = useCallback((id: string | null, select: string | null = null) => { setWanted(id); setSelected(select); }, []);
  return { focus, selected, select: setSelected, open };
}
