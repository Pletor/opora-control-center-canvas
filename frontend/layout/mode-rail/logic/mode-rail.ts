// Ikony záložek módů bez Reactu: kontrakt „Panely editoru“ (docs/panely-editoru.md, tabulka „Módy
// plátna“ a doladění bod 4). Komponenta ikonu jen zobrazí, odvození drží tento soubor, aby se dalo
// otestovat samo o sobě. Vrací se jméno ikony ze sady `ui-kit/icon`, ne znak — Unicode glyfy se
// v každém systému kreslí jinak a leckde chybí, lineární sada drží jednu stopu napříč aplikací.
// Ikona Knihovny sem už nepatří: Knihovna není záložka, otevírá ji `layout/panel-dock/`.
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

/** Ikona pro každý mód plátna (`WorkspaceMode` z shared/types). Neznámé id nesmí lištu shodit. */
export const MODE_ICONS: Record<string, IconName> = {
  structure: "layout-grid",
  text: "type",
  drawing: "pencil",
  map: "map",
};

/** Neznámý mód (chybějící řádek v tabulce, cizí data) dostane ikonu struktury místo prázdného místa. */
export function modeIcon(id: string): IconName {
  return MODE_ICONS[id] ?? "layout-grid";
}
