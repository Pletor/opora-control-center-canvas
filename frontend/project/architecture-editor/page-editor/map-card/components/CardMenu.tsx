import { useEffect, useRef, useState } from "react";

/** Small ⋮ menu on a map card; closes on choice, Escape or a click outside. */
export default function CardMenu({ name, items }: { name: string; items: { label: string; testId: string; onClick: () => void }[] }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close); document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, [open]);
  return <div className="map-card__menu nodrag nopan" ref={root}>
    <button type="button" className="map-card__menu-button" aria-haspopup="menu" aria-expanded={open} aria-label={`Akce pro ${name}`}
      onClick={(event) => { event.stopPropagation(); setOpen(!open); }}>⋮</button>
    {open && <div className="map-card__menu-list" role="menu">
      {items.map((item) => <button key={item.testId} type="button" role="menuitem" className="map-card__menu-item" data-testid={item.testId}
        onClick={(event) => { event.stopPropagation(); setOpen(false); item.onClick(); }}>{item.label}</button>)}
    </div>}
  </div>;
}
