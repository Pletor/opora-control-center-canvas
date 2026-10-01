import type { BlockMenuItem } from "@/editor/node-detail/content/logic/use-block-menu";

/**
 * Paleta nad rozepsaným řádkem: příkazy po `/`, existující uzly po `[[`.
 * Dílek jen vykresluje hotový seznam a hlásí volbu; co položka udělá, ví `BlockOutline`.
 */
export default function BlockMenu({
  kind,
  items,
  active,
}: {
  kind: "slash" | "link";
  items: BlockMenuItem[];
  /** Index zvýrazněné položky; šipky ho posouvají v rodiči. */
  active: number;
}) {
  const current = Math.min(active, items.length - 1);
  return (
    <ul
      className="block-outline__menu"
      role="listbox"
      aria-label={kind === "slash" ? "Paleta příkazů" : "Odkaz na uzel"}
      data-testid="block-menu"
    >
      <li className="block-outline__menu-head" role="presentation">
        {kind === "slash" ? "Příkazy · Esc zavře" : "Existující uzly · Esc zavře"}
      </li>
      {items.map((item, i) => (
        <li key={item.key} role="presentation">
          <button
            type="button"
            role="option"
            aria-selected={i === current}
            className={"block-outline__command" + (i === current ? " block-outline__command--active" : "")}
            onMouseDown={(e) => {
              e.preventDefault();
              item.run();
            }}
          >
            <span>{item.label}</span>
            <kbd className="block-outline__hint">{item.hint}</kbd>
          </button>
        </li>
      ))}
      {!items.length && (
        <li className="block-outline__menu-empty" role="presentation">
          Nic neodpovídá. Esc zavře.
        </li>
      )}
    </ul>
  );
}
