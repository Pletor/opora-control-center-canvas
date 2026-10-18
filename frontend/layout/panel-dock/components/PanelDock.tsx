// Rodič Menu Editoru: u levého okraje pracovní plochy skládá lištu ikon a vedle ní panel zvolené
// sekce. Obsah sekce (Strukturu, Schránku, Nastavení) dostane hotový od App. Obsah, který se nesmí
// zničit (Schránka s rozepsaným textem), dostane v `kept` a drží ho skrytý i při jiné sekci nebo při
// zavřeném menu. Sám drží jen jedno chování, které nepatří žádnému dílku: klik mimo pracovní plochu
// (horní lišta, lišta nástrojů mimo ☰) menu zavře. Klik na plátno nic nezavírá — menu ho nezakrývá
// celé a dá se s ním pracovat vedle. Všechno ostatní jen hlásí nahoru; rozhoduje rodič.
import { useEffect, useRef, type ReactNode } from "react";
import DockRail from "@/layout/panel-dock/components/DockRail";
import PanelDrawer from "@/layout/panel-dock/components/PanelDrawer";
import type { DockSection } from "@/layout/panel-dock/logic/panel-dock";
import "@/layout/panel-dock/styles/panel-dock.css";

export default function PanelDock({
  rail = true,
  section,
  onSelect,
  onClose,
  kept,
  children,
}: {
  /** Lišta je vysunutá; bez ní se menu kreslí jen kvůli `kept` a nic z něj není vidět. */
  rail?: boolean;
  /** Otevřená sekce, nebo `null`, když je vidět jen lišta. */
  section: DockSection | null;
  /** Sekce, jejíž obsah se drží namountovaný (viditelný jen, když je otevřená). */
  kept?: { section: DockSection; content: ReactNode };
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
    <div ref={dock} className={"panel-dock" + (rail ? "" : " panel-dock--closed")} data-testid="panel-dock-root">
      <DockRail section={section} onSelect={onSelect} />
      {/* Dvě pevná místa: běžná sekce a držená sekce. Držená tak při přepnutí nemění pozici a nic se nezničí. */}
      {section && section !== kept?.section ? <PanelDrawer section={section}>{children}</PanelDrawer> : null}
      {kept ? <PanelDrawer section={kept.section} kept={!rail || section !== kept.section}>{kept.content}</PanelDrawer> : null}
    </div>
  );
}
