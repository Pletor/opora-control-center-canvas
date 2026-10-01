// Dílek Šuplík: rám u levého okraje Editoru, ve kterém leží Knihovna nebo Agenti a postupy. Nahoře
// přepínač mezi nimi, pod ním hlavička projektu (dostane ji hotovou v `head`) a pod tím obsah
// (`children`). O Knihovně, Agentech ani o profilu nic neví. Umí dvě věci, které obsah umět nemá:
// zavře se, když uživatel sáhne mimo pracovní plochu (plátno šuplík nezakrývá, proto klik na plátno
// nic nezavře), a při tažení položky zprůhlední a pustí myš skrz sebe, aby šlo položku pustit i na
// plátno pod ním. Přepnutí i zavření jen hlásí nahoru — rozhoduje rodič.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { DOCK_PANELS, type DockPanel } from "@/layout/panel-dock/logic/panel-dock";
import "@/layout/panel-dock/styles/panel-dock.css";

export default function PanelDrawer({
  panel,
  onSelect,
  onClose,
  head,
  children,
}: {
  panel: DockPanel;
  /** Segment v šuplíku: stejné přepnutí jako tlačítka v liště. */
  onSelect: (panel: DockPanel) => void;
  onClose: () => void;
  /** Hlavička projektu a karta profilu; šuplík je jen posadí pod přepínač. */
  head?: ReactNode;
  children: ReactNode;
}) {
  const drawer = useRef<HTMLElement>(null);
  const [dragging, setDragging] = useState(false);
  const close = useRef(onClose);
  close.current = onClose;
  const label = DOCK_PANELS.find((item) => item.key === panel)?.label ?? "";

  // Klik mimo pracovní plochu (lišta nástrojů, horní lišta) šuplík zavře; tlačítka panelů mají
  // vlastní přepnutí. Klik na plátno ani do inspektoru ne: šuplík je nezakrývá, dá se s ním pracovat.
  useEffect(() => {
    const down = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (drawer.current?.contains(target) || target.closest("[data-panel-anchor]")) return;
      const frame = drawer.current?.parentElement;
      if (frame?.contains(target)) return;
      close.current();
    };
    document.addEventListener("pointerdown", down, true);
    return () => document.removeEventListener("pointerdown", down, true);
  }, []);

  // Tažení: modifikátor přijde až v dalším snímku — kdyby šuplík přestal brát myš hned při
  // `dragstart`, prohlížeč by tažení zrušil. Konec tažení se čte na `document`, protože `drop`
  // obslouží plátno; šuplík po puštění zůstává otevřený pro další položku.
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
      ref={drawer}
      id="panel-dock"
      className={"panel-drawer" + (dragging ? " panel-drawer--dragging" : "")}
      aria-label={label}
      data-testid="panel-dock"
      onDragStart={startDrag}
    >
      <div className="panel-drawer__top">
        <div className="panel-drawer__switch" role="tablist" aria-label="Obsah šuplíku">
          {DOCK_PANELS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={panel === item.key}
              className={"panel-drawer__segment" + (panel === item.key ? " panel-drawer__segment--active" : "")}
              data-testid={"drawer-switch-" + item.key}
              onClick={() => { if (panel !== item.key) onSelect(item.key); }}
            >
              {item.label}
            </button>
          ))}
        </div>
        {head}
      </div>
      <div className="panel-drawer__body">{children}</div>
    </section>
  );
}
