import { useEffect, useRef, useState } from "react";
import "@/layout/account-corner/styles/account-corner.css";

/**
 * Levý dolní roh: tlačítko aplikace, po kliknutí popup menu.
 * Dnes jediná položka: Nastavení. Další (jazyk, nápověda, účet) přibudou postupně.
 */
export default function AccountCorner({ onSettings }: { onSettings: () => void }) {
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => {
      if (!anchor.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div className="account-corner" ref={anchor}>
      {open && (
        <div id="account-menu" className="menu account-menu" role="group" aria-label="Menu aplikace">
          <div className="menu-head">Opora Canvas · lokálně</div>
          <button
            type="button"
            className="menu-item"
            onClick={() => {
              setOpen(false);
              onSettings();
            }}
          >
            Nastavení
            <small>Obecné, Plátno, Projekt, Skills, Connectors</small>
          </button>
        </div>
      )}
      <button
        type="button"
        className="account-button"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls="account-menu"
        title="Menu aplikace"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="account-mark" aria-hidden="true">O</span>
        <span className="account-label">Opora</span>
      </button>
    </div>
  );
}
