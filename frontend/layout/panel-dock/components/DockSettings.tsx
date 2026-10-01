// Dílek Nastavení menu: co platí pro všechny ostatní sekce. Nahoře karta profilu projektu (dostane
// ji hotovou v `profileCard`, vždy rozbalenou), pod ní filtr katalogu „Pro tento projekt / Vše“.
// Filtr je preference aplikace, ne projektu; volbu hlásí `onScope` nahoru a ukládá ji rodič.
import type { ReactNode } from "react";
import CatalogScopeBar from "@/layout/panel-dock/components/CatalogScopeBar";
import type { CatalogScope } from "@/layout/panel-dock/logic/panel-drawer";

export default function DockSettings({
  profileCard,
  scope,
  filtering,
  onScope,
}: {
  profileCard: ReactNode;
  scope: CatalogScope;
  /** Profil je nastavený, takže filtr má co zužovat. */
  filtering: boolean;
  onScope: (scope: CatalogScope) => void;
}) {
  return (
    <div className="dock-settings" data-testid="dock-settings">
      <section className="dock-settings__group" aria-label="Profil projektu">
        <h3 className="dock-settings__heading">Profil projektu</h3>
        {profileCard}
      </section>
      <section className="dock-settings__group" aria-label="Filtr katalogu">
        <h3 className="dock-settings__heading">Katalog</h3>
        <CatalogScopeBar scope={scope} onScope={onScope} />
        <p className="dock-settings__hint">
          {filtering
            ? "Knihovna, Agenti i Postupy ukážou buď jen to, co sedí k profilu projektu, nebo vše. Volba platí pro celou aplikaci."
            : "Bez profilu se nic nefiltruje: Knihovna, Agenti i Postupy ukazují vše. Nastavte profil výše a filtr začne zužovat."}
        </p>
      </section>
    </div>
  );
}
