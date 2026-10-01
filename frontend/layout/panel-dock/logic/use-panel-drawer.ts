// Vazba filtru katalogu na React: drží volbu „Pro tento projekt / Vše“ (uloženou jednou pro
// aplikaci) a dočasné ukázání prvků mimo profil (jen paměť sezení). Volá ho rodič (App) jednou,
// vedle `usePanelDock`, a rozdá výsledek v props Knihovně, Agentům, Postupům i Nastavení.
import { useCallback, useEffect, useState } from "react";
import { readCatalogScope, writeCatalogScope, type CatalogScope } from "./panel-drawer";

export type PanelDrawerApi = {
  scope: CatalogScope;
  setScope: (scope: CatalogScope) => void;
  showOutside: boolean;
  toggleOutside: () => void;
};

export function usePanelDrawer(): PanelDrawerApi {
  const [scope, setScopeState] = useState<CatalogScope>(readCatalogScope);
  const [showOutside, setShowOutside] = useState(false);
  useEffect(() => { writeCatalogScope(scope); }, [scope]);
  const setScope = useCallback((next: CatalogScope) => {
    setScopeState(next);
    setShowOutside(false);
  }, []);
  const toggleOutside = useCallback(() => setShowOutside((current) => !current), []);
  return { scope, setScope, showOutside, toggleOutside };
}
