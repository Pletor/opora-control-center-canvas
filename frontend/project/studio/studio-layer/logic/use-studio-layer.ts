// Vrstva Studia v adrese (`studioLayer`): přání člověka se drží v paměti, platná vrstva se odvodí z domény zanoření
// a po načtení grafu se adresa srovná (na úrovni projektu MODEL není, parametr zmizí).
import { useCallback, useEffect, useState } from "react";
import { effectiveLayer, readStudioLayer, STUDIO_LAYER_PARAM, withStudioLayer, type StudioLayer } from "./studio-layer";

export function useStudioLayer(domain: string | null, loaded: boolean) {
  const [wanted, setWanted] = useState<StudioLayer>(() => readStudioLayer(new URLSearchParams(location.search)));
  const layer = effectiveLayer(wanted, domain);
  useEffect(() => {
    if (!loaded) return;
    const current = new URLSearchParams(location.search), next = withStudioLayer(current, layer);
    if (next.get(STUDIO_LAYER_PARAM) !== current.get(STUDIO_LAYER_PARAM)) history.replaceState(null, "", "/?" + next);
  }, [loaded, layer]);
  const choose = useCallback((next: StudioLayer) => setWanted(next), []);
  return { layer, choose };
}
