import "../styles/pletor-settings.css";

/**
 * Ozubené kolo vedle přepínače Poslech: otevře a zavře nastavení Pletora (hlas, čtení, mozek). Otevřenost drží App,
 * aby kolo v horní liště, v HUD i v popupu ovládalo jeden panel. `data-pletor-settings-toggle` panel pozná, aby klik
 * na kolo nebral jako klik mimo.
 */
export default function PletorSettingsButton({ open, onToggle, tone = "dark" }: { open: boolean; onToggle: () => void; tone?: "bar" | "dark" }) {
  return (
    <button type="button" className={`pletor-settings__toggle pletor-settings__toggle--${tone}` + (open ? " pletor-settings__toggle--open" : "")}
      aria-label="Nastavení Pletora" title="Nastavení Pletora: hlas, čtení, mozek" aria-haspopup="dialog" aria-expanded={open}
      data-pletor-settings-toggle onClick={onToggle}>
      <svg className="pletor-settings__gear" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
      </svg>
    </button>
  );
}
