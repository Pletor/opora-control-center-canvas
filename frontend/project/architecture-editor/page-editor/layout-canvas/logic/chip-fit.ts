// Kolik štítků prvků logiky se vejde do boxu na plátně 2 (vrstva Logika); zbytek ukáže „+N“. Box s vnořenými boxy
// (nebo příliš nízký) nese štítky v řádku hlavičky, aby nepřetekly přes děti. Bez Reactu, test vedle.
import { GAP_PX, ROW_PITCH } from "./layout-grid";

// shortcut: odhad z šířky papíru 900 px a štítku ~170 px místo měření DOM; když štítky začnou přetékat, měř ResizeObserverem.
const PAGE_PX = 900, CHIP_PX = 170, CHIP_ROW_PX = 26, HEAD_PX = 24, NAME_PX = 150, PAD_PX = 12;

/** `share` = podíl šířky papíru, který box zabírá (součin `w / 12` po předcích), `rows` = výška boxu v řádcích. */
export function chipFit(count: number, share: number, rows: number, leaf: boolean): { shown: number; head: boolean } {
  const width = share * PAGE_PX - PAD_PX;
  const lines = leaf ? Math.floor((rows * ROW_PITCH - GAP_PX - HEAD_PX - PAD_PX) / CHIP_ROW_PX) : 0;
  const head = lines < 1;
  const room = head ? Math.max(0, Math.floor((width - NAME_PX) / CHIP_PX)) : Math.max(1, Math.floor(width / CHIP_PX)) * lines;
  return { shown: count <= room ? count : Math.max(0, room - 1), head };
}
