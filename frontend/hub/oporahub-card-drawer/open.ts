// Veřejný vstup jednotného detailu karty (kontrakt nočního plánu §6): plátno, Velín, odznaky i OporaHub
// volají `openCardDrawer(nodeId, tab?)` odsud. Implementace a stav leží v `logic/card-drawer-store.ts`.
export { openCardDrawer, closeCardDrawer, CARD_TABS, type CardTab } from "./logic/card-drawer-store";
