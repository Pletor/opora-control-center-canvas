// Dílek ☰: jediné tlačítko menu v liště nástrojů, hned před záložkami módů. Otevře u levého okraje
// lištu ikon (a poslední sekci), druhý klik menu zavře. Je zároveň kotva (`data-panel-anchor`):
// klik na něj menu nezavírá jako klik mimo. Nic nedrží — otevřenost dostane v props, klik hlásí nahoru.
import DockIcon from "@/layout/panel-dock/components/DockIcon";
import "@/layout/panel-dock/styles/panel-dock.css";

export default function MenuButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={"dock-menu" + (open ? " dock-menu--open" : "")}
      aria-label="Menu Editoru"
      aria-expanded={open}
      aria-controls="panel-dock-rail"
      title="Menu Editoru: Struktura, Schránka, Nastavení"
      data-panel-anchor="menu"
      data-testid="dock-menu"
      onClick={onToggle}
    >
      <DockIcon name="menu" size={20} />
    </button>
  );
}
