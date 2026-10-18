// Dílek Struktury: jedna skupina seznamu vrstev (Sektory / Uzly mimo sektor / Oblasti). Hlavička
// se dá kliknutím sbalit, pod ní jsou řádky stromu. Dílek nic nepočítá ani neukládá: řádky dostane
// hotové v props a klik hlásí callbackem nahoru.
//
// Znaménko skupiny je jedna a táž šipka, jen otočená: zavřená míří doprava („je tu ještě něco“),
// otevřená dolů („koukáš dovnitř“). Je to stejný pohyb, jaký zná každý strom souborů — proto jedna
// ikona s variantou, ne dva různé znaky.
import { layerKindIcon } from "@/layout/structure-panel/logic/structure-panel";
import Icon from "@/ui-kit/icon/components/Icon";
import type { LayerGroup, LayerRow } from "@/layout/structure-panel/logic/layer-list";

/** Odsazení stromu je 24px na úroveň a jde přes modifikátor třídy, ne přes inline styl;
    od páté úrovně se hloubka drží na místě, aby řádek nezmizel za pravou hranou panelu. */
const MAX_DEPTH_CLASS = 4;
const depthClass = (depth: number): string => "structure-panel__row--depth-" + Math.min(depth, MAX_DEPTH_CLASS);

export default function StructureLayerGroup({
  group,
  empty,
  collapsed,
  onToggle,
  onOpen,
}: {
  group: LayerGroup;
  /** Věta pro prázdnou skupinu; říká, že se nic neztratilo, jen tam nic není. */
  empty: string;
  collapsed: boolean;
  onToggle: () => void;
  onOpen: (id: string) => void;
}) {
  return (
    <section className={"structure-panel__group" + (collapsed ? " structure-panel__group--collapsed" : "")}>
      <button
        type="button"
        className="structure-panel__group-head"
        aria-expanded={!collapsed}
        data-testid={"structure-group-" + group.id}
        onClick={onToggle}
      >
        <Icon
          className={"structure-panel__group-sign" + (collapsed ? "" : " structure-panel__group-sign--open")}
          name="chevron-right"
          size={16}
        />
        <span className="structure-panel__group-label">{group.label}</span>
        <small className="structure-panel__group-count">{group.rows.length}</small>
      </button>
      {!collapsed && (group.rows.length ? (
        <div className="structure-panel__rows">
          {group.rows.map((row) => <Row key={row.id} row={row} onOpen={onOpen} />)}
        </div>
      ) : (
        <p className="structure-panel__empty">{empty}</p>
      ))}
    </section>
  );
}

/** Jeden řádek stromu: odsazení podle zanoření, žeton druhu vlevo, domeček u vrstvy ležící rovnou
    v projektu a tichá značka „skryto“ u uzavřené karty (ztlumí se celý řádek, ne jen text). */
function Row({ row, onOpen }: { row: LayerRow; onOpen: (id: string) => void }) {
  const className =
    "structure-panel__row" +
    " " + depthClass(row.depth) +
    (row.depth ? " structure-panel__row--nested" : "") +
    (row.isRoot ? " structure-panel__row--root" : "") +
    (row.hidden ? " structure-panel__row--hidden" : "");
  return (
    <button
      type="button"
      className={className}
      title={row.hidden ? "Karta je uzavřená." : "Otevřít vrstvu na plátně"}
      data-testid={"structure-layer-" + row.id}
      onClick={() => onOpen(row.id)}
    >
      <span className="structure-panel__row-kind">
        <Icon name={layerKindIcon(row.kind)} size={16} />
      </span>
      <span className="structure-panel__row-name">{row.name}</span>
      {row.isRoot && (
        <Icon className="structure-panel__row-home" name="home" size={16} label="Leží rovnou v projektu" />
      )}
      {row.hidden && <span className="structure-panel__row-flag" aria-label="Uzavřená karta">skryto</span>}
    </button>
  );
}
