// Dílek Zavěšený panel: rám, ve kterém visí Knihovna nebo Agenti a postupy pod svým tlačítkem.
// Obsah dostane hotový v `children` a o Knihovně ani o Agentech nic neví. Umí tři věci, které
// obsah umět nemá: najde tlačítko, pod kterým visí, a namíří na jeho střed šipku; zavře se, když
// uživatel sáhne jinam; a při tažení položky zprůhlední a pustí myš skrz sebe, aby šlo položku
// pustit i na plátno, které zakrývá. Zavření jen hlásí `onClose` nahoru — rozhoduje rodič.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { dropdownPlacement, type DockPanel } from "@/layout/panel-dock/logic/panel-dock";
import "@/layout/panel-dock/styles/panel-dock.css";

export default function PanelDropdown({
  panel,
  label,
  onClose,
  children,
}: {
  panel: DockPanel;
  label: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const dock = useRef<HTMLElement>(null);
  const [dragging, setDragging] = useState(false);
  // Posluchače se vážou jednou; aktuální `onClose` se čte z ref.
  const close = useRef(onClose);
  close.current = onClose;

  // Poloha: rám je rodič dropdownu, kotva je tlačítko v liště nad ním. Obojí se měří v okně,
  // výsledek se píše přímo do stylu, aby změna polohy nepřekreslovala obsah panelu.
  useLayoutEffect(() => {
    const place = () => {
      const element = dock.current;
      const frame = element?.parentElement;
      const anchor = document.querySelector<HTMLElement>(`[data-panel-anchor="${panel}"]`);
      if (!element || !frame || !anchor) return;
      const frameBox = frame.getBoundingClientRect();
      const anchorBox = anchor.getBoundingClientRect();
      const { left, arrow } = dropdownPlacement(anchorBox.left + anchorBox.width / 2 - frameBox.left, frameBox.width);
      element.style.left = left + "px";
      element.style.setProperty("--panel-dock-arrow", arrow + "px");
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [panel]);

  // Klik mimo panel a mimo jeho tlačítka panel zavře. Zachytává se už při sestupu, aby ho nevzal
  // dílek, který si `pointerdown` zastaví (plátno, kreslení); tlačítka mají vlastní přepnutí,
  // jinak by se panel zavřel a hned zase otevřel.
  useEffect(() => {
    const down = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (dock.current?.contains(target) || target.closest("[data-panel-anchor]")) return;
      close.current();
    };
    document.addEventListener("pointerdown", down, true);
    return () => document.removeEventListener("pointerdown", down, true);
  }, []);

  // Tažení: modifikátor přijde až v dalším snímku — kdyby panel přestal brát myš hned při
  // `dragstart`, prohlížeč by tažení zrušil. Konec tažení se čte na `document`, protože plátno
  // `drop` samo obslouží a panel po puštění zůstává otevřený.
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
      ref={dock}
      id="panel-dock"
      className={"panel-dock" + (dragging ? " panel-dock--dragging" : "")}
      aria-label={label}
      data-testid="panel-dock"
      onDragStart={startDrag}
    >
      <span className="panel-dock__arrow" aria-hidden="true" />
      {children}
    </section>
  );
}
