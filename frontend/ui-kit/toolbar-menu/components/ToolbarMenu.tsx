// Tlačítko lišty s rozbalovací nabídkou (⋯ další pohledy, + Přidat). Nabídka není modál: zavře ji výběr,
// klik mimo nebo Esc a fokus se vrátí na tlačítko. Položky jsou hotová data, výběr bublá callbackem.
import { useEffect, useRef, useState, type ReactNode } from "react";
import "../styles/toolbar-menu.css";

export type ToolbarMenuItem = { key: string; label: string; hint?: string; shortcut?: string; glyph?: ReactNode; disabled?: boolean; active?: boolean };

export default function ToolbarMenu({ label, title, heading, items, onSelect, active = false, align = "start", disabled = false }: {
  label: ReactNode; title: string; heading?: string; items: ToolbarMenuItem[]; onSelect: (key: string) => void;
  active?: boolean; align?: "start" | "end"; disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); button.current?.focus(); } };
    window.addEventListener("pointerdown", away);
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("pointerdown", away); window.removeEventListener("keydown", key); };
  }, [open]);
  return (
    <div className="toolbar-menu" ref={root}>
      <button ref={button} type="button" className={"toolbar-menu__button" + (active ? " toolbar-menu__button--active" : "")}
        aria-haspopup="menu" aria-expanded={open} title={title} disabled={disabled} onClick={() => setOpen((value) => !value)}>
        {label}
      </button>
      {open && (
        <div className={"toolbar-menu__list toolbar-menu__list--" + align} role="menu" aria-label={title}>
          {heading && <div className="toolbar-menu__heading">{heading}</div>}
          {items.map((item) => (
            <button key={item.key} type="button" role="menuitem" disabled={item.disabled} title={item.hint}
              className={"toolbar-menu__item" + (item.active ? " toolbar-menu__item--active" : "")}
              onClick={() => { setOpen(false); onSelect(item.key); }}>
              {item.glyph && <span className="toolbar-menu__glyph" aria-hidden="true">{item.glyph}</span>}
              <span className="toolbar-menu__label">{item.label}</span>
              {item.shortcut && <kbd className="toolbar-menu__shortcut">{item.shortcut}</kbd>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
