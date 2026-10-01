// Dílek Panel sekce: rám vedle lišty ikon, ve kterém leží Knihovna, Agenti, Postupy nebo Nastavení.
// Nahoře jediná hlavička panelu (název sekce a zkratka) a pod ní obsah (`children`). Projekt a jeho
// profil tu nejsou: patří do sekce Nastavení, aby nebraly místo a pozornost obsahu sekce. O obsahu nic neví. Umí jednu věc, kterou obsah umět nemá:
// při tažení položky zprůhlední a pustí myš skrz sebe, aby šlo položku pustit i na plátno pod ním.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { sectionInfo, type DockSection } from "@/layout/panel-dock/logic/panel-dock";

export default function PanelDrawer({
  section,
  children,
}: {
  section: DockSection;
  children: ReactNode;
}) {
  const [dragging, setDragging] = useState(false);
  const info = sectionInfo(section);

  // Tažení: modifikátor přijde až v dalším snímku — kdyby panel přestal brát myš hned při
  // `dragstart`, prohlížeč by tažení zrušil. Konec tažení se čte na `document`, protože `drop`
  // obslouží plátno; panel po puštění zůstává otevřený pro další položku.
  const frame = useRef(0);
  useEffect(() => {
    const end = () => {
      cancelAnimationFrame(frame.current);
      setDragging(false);
    };
    document.addEventListener("dragend", end, true);
    document.addEventListener("drop", end, true);
    return () => {
      cancelAnimationFrame(frame.current);
      document.removeEventListener("dragend", end, true);
      document.removeEventListener("drop", end, true);
    };
  }, []);
  const startDrag = () => {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => setDragging(true));
  };

  return (
    <section
      id="panel-dock"
      className={"panel-drawer" + (dragging ? " panel-drawer--dragging" : "")}
      aria-label={info.label}
      data-testid="panel-dock"
      data-section={section}
      onDragStart={startDrag}
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
