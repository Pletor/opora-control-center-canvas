// Dílek STRÁNKY: jedna skupina seznamu vrstev (Sektory / Uzly mimo sektor / Oblasti). Hlavička
// se dá kliknutím sbalit, pod ní jsou řádky stromu. Dílek nic nepočítá ani neukládá: řádky dostane
// hotové v props a klik hlásí callbackem nahoru.
//
// Znaménko skupiny je jedna a táž šipka, jen otočená: zavřená míří doprava („je tu ještě něco“),
// otevřená dolů („koukáš dovnitř“). Je to stejný pohyb, jaký zná každý strom souborů — proto jedna
// ikona s variantou, ne dva různé znaky.
import { layerKindIcon } from "@/layout/library-navbar/logic/library-navbar";
import Icon from "@/ui-kit/icon/components/Icon";
import type { LayerGroup, LayerRow } from "@/layout/library-navbar/logic/layer-list";

/** Odsazení stromu je 24px na úroveň a jde přes modifikátor třídy, ne přes inline styl;
    od páté úrovně se hloubka drží na místě, aby řádek nezmizel za pravou hranou panelu. */
const MAX_DEPTH_CLASS = 4;
const depthClass = (depth: number): string => "library-navbar__row--depth-" + Math.min(depth, MAX_DEPTH_CLASS);

export default function LibraryLayerGroup({
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
    <section className={"library-navbar__group" + (collapsed ? " library-navbar__group--collapsed" : "")}>
      <button
        type="button"
        className="library-navbar__group-head"
        aria-expanded={!collapsed}
        data-testid={"library-group-" + group.id}
        onClick={onToggle}
      >
        <Icon
          className={"library-navbar__group-sign" + (collapsed ? "" : " library-navbar__group-sign--open")}
          name="chevron-right"
          size={16}
        />
        <span className="library-navbar__group-label">{group.label}</span>
        <small className="library-navbar__group-count">{group.rows.length}</small>
      </button>
      {!collapsed && (group.rows.length ? (
        <div className="library-navbar__rows">
          {group.rows.map((row) => <Row key={row.id} row={row} onOpen={onOpen} />)}
        </div>
      ) : (
        <p className="library-navbar__empty">{empty}</p>
      ))}
    </section>
  );
}

/** Jeden řádek stromu: odsazení podle zanoření, žeton druhu vlevo, domeček u vrstvy ležící rovnou
    v projektu a tichá značka „skryto“ u uzavřené karty (ztlumí se celý řádek, ne jen text). */
function Row({ row, onOpen }: { row: LayerRow; onOpen: (id: string) => void }) {
  const className =
    "library-navbar__row" +
    " " + depthClass(row.depth) +
    (row.depth ? " library-navbar__row--nested" : "") +
    (row.isRoot ? " library-navbar__row--root" : "") +
    (row.hidden ? " library-navbar__row--hidden" : "");
  return (
    <button
      type="button"
      className={className}
      title={row.hidden ? "Karta je uzavřená." : "Otevřít vrstvu na plátně"}
      data-testid={"library-layer-" + row.id}
      onClick={() => onOpen(row.id)}
    >
      <span className="library-navbar__row-kind">
        <Icon name={layerKindIcon(row.kind)} size={16} />
      </span>
      <span className="library-navbar__row-name">{row.name}</span>
      {row.isRoot && (
        <Icon className="library-navbar__row-home" name="home" size={16} label="Leží rovnou v projektu" />
      )}
      {row.hidden && <span className="library-navbar__row-flag" aria-label="Uzavřená karta">skryto</span>}
    </button>
  );
}
