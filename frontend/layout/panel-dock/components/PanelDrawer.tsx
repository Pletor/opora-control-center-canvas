// Dílek Panel sekce: rám vedle lišty ikon, ve kterém leží Struktura, Schránka nebo Nastavení. Nahoře
// jediná hlavička panelu (název sekce a zkratka) a pod ní obsah (`children`); o obsahu nic neví. Sekce
// s vlastním vnitřním menu (Schránka) dostane široký panel. Skrytý panel (`kept`) zůstává v DOM jen
// proto, aby se v něm neztratil rozepsaný text; nemá id ani přístupné jméno, nic neohlašuje.
import type { ReactNode } from "react";
import { sectionInfo, type DockSection } from "@/layout/panel-dock/logic/panel-dock";

export default function PanelDrawer({ section, kept = false, children }: {
  section: DockSection;
  /** Panel je skrytý, ale jeho obsah se drží (Schránka s rozepsaným textem). */
  kept?: boolean;
  children: ReactNode;
}) {
  const info = sectionInfo(section);
  return (
    <section
      id={kept ? undefined : "panel-dock"}
      className={"panel-drawer" + (info.wide ? " panel-drawer--wide" : "") + (kept ? " panel-drawer--kept" : "")}
      aria-label={kept ? undefined : info.label}
      aria-hidden={kept || undefined}
      data-testid={kept ? "panel-dock-kept" : "panel-dock"}
      data-section={section}
    >
      <div className="panel-drawer__top">
        <header className="panel-drawer__head">
          <h2 className="panel-drawer__title">{info.label}</h2>
          {info.shortcut && <kbd className="panel-drawer__kbd">{info.shortcut}</kbd>}
        </header>
      </div>
      <div className="panel-drawer__body">{children}</div>
    </section>
  );
}
