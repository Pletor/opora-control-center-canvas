// Úroveň detailu karty (docs/navrhy/2026-10-14-vykon-platna.md, oprava 4). Oddálené plátno ukazuje
// stovky karet najednou a editory v nich stejně nejdou přečíst; karta pod prahem zoomu kreslí jen hlavu,
// název, stav a úchyty, aby vazby zůstaly připojené. Vybraná karta a karta s rozepsaným textem zůstávají
// celé vždy, jinak by člověku zmizelo, na čem právě pracuje.

/** Pod tímhle zoomem jsou popisy bloků menší než čitelné písmo; karta se zjednoduší. */
export const FAR_ZOOM = 0.45;

export type CardDetail = "full" | "far";

/**
 * Selektor pro `useStore` React Flow: vrací jediný boolean, takže se karta překreslí jen při překročení
 * prahu, ne v každém snímku zoomu.
 */
export const farZoomSelector = (store: { transform: readonly [number, number, number] }) => store.transform[2] < FAR_ZOOM;

/** Detail celé karty: vybraná karta je celá v každém zoomu. */
export const cardDetail = (far: boolean, selected: boolean): CardDetail => (far && !selected ? "far" : "full");

/**
 * Editory portu (rozhodnutí, navazující karta) jsou u vybrané karty. Po zrušení výběru zůstane namontovaný
 * editor, který je rozepsaný nebo má fokus, dokud se neuloží nebo neopustí; jinak by rozepsané zmizelo.
 */
export const portEditorsShown = (detail: "full" | "row" | "far", held: boolean): boolean => detail === "full" || held;

/** Detail bloků: rozepsaný nebo zaměřený text drží bloky celé i v oddálení, aby se draft neztratil. */
export const blocksDetail = (detail: CardDetail, holding: boolean): CardDetail => (detail === "far" && !holding ? "far" : "full");
