// Vazba šuplíku na React: drží volbu filtru (uloženou jednou pro aplikaci) a dvě hodnoty jen pro
// toto sezení — dočasné ukázání prvků mimo profil a kartu profilu (otevřená ke změně, nebo odložená
// tlačítkem „Teď ne“). Volá ho rodič (App) jednou, vedle `usePanelDock`, a rozdá výsledek v props.
import { useCallback, useEffect, useState } from "react";
import { readCatalogScope, writeCatalogScope, type CatalogScope } from "./panel-drawer";

export type PanelDrawerApi = {
  scope: CatalogScope;
  setScope: (scope: CatalogScope) => void;
  showOutside: boolean;
  toggleOutside: () => void;
  /** Karta profilu otevřená odkazem „Změnit“. */
  editingProfile: boolean;
  setEditingProfile: (editing: boolean) => void;
  /** „Teď ne, ukázat vše“: karta nenastaveného profilu se do konce sezení sbalí do hlavičky. */
  profileDismissed: boolean;
  dismissProfile: () => void;
};

export function usePanelDrawer(): PanelDrawerApi {
  const [scope, setScopeState] = useState<CatalogScope>(readCatalogScope);
  const [showOutside, setShowOutside] = useState(false);
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileDismissed, setProfileDismissed] = useState(false);
  useEffect(() => { writeCatalogScope(scope); }, [scope]);
  const setScope = useCallback((next: CatalogScope) => {
    setScopeState(next);
    setShowOutside(false);
  }, []);
  const toggleOutside = useCallback(() => setShowOutside((current) => !current), []);
  const dismissProfile = useCallback(() => {
    setProfileDismissed(true);
    setEditingProfile(false);
  }, []);
  return { scope, setScope, showOutside, toggleOutside, editingProfile, setEditingProfile, profileDismissed, dismissProfile };
}
