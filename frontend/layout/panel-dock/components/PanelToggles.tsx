// Dílek Přepínače panelů: dvě tlačítka v liště nástrojů hned za záložkami módů — Knihovna a
// Agenti a postupy. Tlačítko je zároveň kotva: dropdown si podle `data-panel-anchor` najde, pod
// čím visí, a namíří na jeho střed šipku. Dílek nic nedrží ani neukládá — který panel je otevřený,
// dostává v props a klik hlásí `onToggle` nahoru; o tom, co se otevře, rozhoduje rodič.
import Icon from "@/ui-kit/icon/components/Icon";
import { DOCK_PANELS, type DockPanel } from "@/layout/panel-dock/logic/panel-dock";
import "@/layout/panel-dock/styles/panel-dock.css";

export default function PanelToggles({ open, onToggle }: { open: DockPanel | null; onToggle: (panel: DockPanel) => void }) {
  return (
    <div className="panel-toggles" role="group" aria-label="Panely Editoru">
      {DOCK_PANELS.map((panel) => (
        <button
          key={panel.key}
          type="button"
          className={"panel-toggles__button" + (open === panel.key ? " panel-toggles__button--open" : "")}
          aria-expanded={open === panel.key}
          aria-controls="panel-dock"
          title={`${panel.label} (${panel.shortcut})`}
          data-panel-anchor={panel.key}
          data-testid={"panel-toggle-" + panel.key}
          onClick={() => onToggle(panel.key)}
        >
          <Icon name={panel.icon} size={16} />
          <span className="panel-toggles__label">{panel.label}</span>
          <kbd className="panel-toggles__kbd">{panel.shortcut}</kbd>
        </button>
      ))}
    </div>
  );
}
