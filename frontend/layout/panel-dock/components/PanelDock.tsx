// Rodič Menu Editoru: u levého okraje pracovní plochy skládá lištu ikon a vedle ní panel zvolené
// sekce. Obsah sekce (Knihovnu, Agenty, Postupy, Nastavení) i hlavičku projektu dostane hotové od
// App; sám drží jen jedno chování, které nepatří žádnému dílku: klik mimo pracovní plochu (horní
// lišta, lišta nástrojů mimo ☰) menu zavře. Klik na plátno nic nezavírá — menu ho nezakrývá celé
// a dá se s ním pracovat vedle. Všechno ostatní jen hlásí nahoru; rozhoduje rodič.
import { useEffect, useRef, type ReactNode } from "react";
import DockRail from "@/layout/panel-dock/components/DockRail";
import PanelDrawer from "@/layout/panel-dock/components/PanelDrawer";
import type { DockSection } from "@/layout/panel-dock/logic/panel-dock";
import "@/layout/panel-dock/styles/panel-dock.css";

export default function PanelDock({
  section,
  head,
  onSelect,
  onClose,
  children,
}: {
  /** Otevřená sekce, nebo `null`, když je vidět jen lišta. */
  section: DockSection | null;
  head?: ReactNode;
  onSelect: (section: DockSection) => void;
  onClose: () => void;
  /** Obsah otevřené sekce. */
  children?: ReactNode;
}) {
  const dock = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    const down = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest("[data-panel-anchor]")) return;
      // Rám pracovní plochy (plátno, inspektor, menu samo) menu nezavírá.
      const frame = dock.current?.parentElement;
      if (frame?.contains(target)) return;
      close.current();
    };
    document.addEventListener("pointerdown", down, true);
    return () => document.removeEventListener("pointerdown", down, true);
  }, []);

  return (
    <div ref={dock} className="panel-dock" data-testid="panel-dock-root">
      <DockRail section={section} onSelect={onSelect} />
      {section && (
        <PanelDrawer section={section} head={head}>
          {children}
        </PanelDrawer>
      )}
    </div>
  );
}
