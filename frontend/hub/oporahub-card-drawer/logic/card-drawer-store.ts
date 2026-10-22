// Jediný detail karty v celé aplikaci: kdo ho chce otevřít (odznak na plátně, dvojklik, Velín, OporaHub),
// zavolá `openCardDrawer(nodeId, tab?)`. Stav drží tento malý obchod mimo React a zrcadlí ho do URL
// (`?ohCard=<id>&ohTab=<záložka>`), aby šel detail sdílet odkazem i obnovit po načtení stránky.
export const CARD_TABS = ["spec", "steps", "lens", "run", "review", "history"] as const;
export type CardTab = typeof CARD_TABS[number];
export type DrawerState = { nodeId: string; tab: CardTab; nonce: number } | null;
export type DrawerLocation = { read(): string; write(search: string): void };

const isTab = (value: string | null): value is CardTab => !!value && (CARD_TABS as readonly string[]).includes(value);

/** Přečte přímý odkaz; neznámá záložka spadne na Zadání, prázdné id znamená zavřený detail. */
export function parseDrawerLink(search: string): { nodeId: string; tab: CardTab } | null {
  const params = new URLSearchParams(search);
  const nodeId = (params.get("ohCard") ?? "").trim().slice(0, 200);
  if (!nodeId) return null;
  const tab = params.get("ohTab");
  return { nodeId, tab: isTab(tab) ? tab : "spec" };
}

/** Zapíše stav detailu do query; ostatní parametry (prostředí, vrstva, uzel) zůstávají beze změny. */
export function writeDrawerLink(search: string, state: DrawerState): string {
  const params = new URLSearchParams(search);
  if (state) { params.set("ohCard", state.nodeId); params.set("ohTab", state.tab); }
  else { params.delete("ohCard"); params.delete("ohTab"); }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function browserLocation(): DrawerLocation | null {
  if (typeof window === "undefined" || typeof history === "undefined") return null;
  return {
    read: () => window.location.search,
    write: search => {
      const url = `${window.location.pathname}${search}${window.location.hash}`;
      if (url !== `${window.location.pathname}${window.location.search}${window.location.hash}`) history.replaceState(history.state, "", url);
    },
  };
}

export function createCardDrawerStore(location: DrawerLocation | null = null) {
  const initial = location ? parseDrawerLink(location.read()) : null;
  let state: DrawerState = initial ? { ...initial, nonce: 1 } : null;
  const listeners = new Set<() => void>();
  const publish = (next: DrawerState) => {
    state = next;
    if (location) location.write(writeDrawerLink(location.read(), state));
    listeners.forEach(listener => listener());
  };
  return {
    get: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    open(nodeId: string, tab?: CardTab) {
      const id = nodeId.trim();
      if (!id) return;
      publish({ nodeId: id, tab: tab && isTab(tab) ? tab : state?.nodeId === id ? state.tab : "spec", nonce: (state?.nonce ?? 0) + 1 });
    },
    setTab(tab: CardTab) { if (state && state.tab !== tab && isTab(tab)) publish({ ...state, tab }); },
    close() { if (state) publish(null); },
  };
}
export type CardDrawerStore = ReturnType<typeof createCardDrawerStore>;

export const cardDrawerStore = createCardDrawerStore(browserLocation());

/** Otevře jednotný detail karty (volitelně na záložce). Bezpečné volat odkudkoli, i mimo React. */
export function openCardDrawer(nodeId: string, tab?: CardTab): void {
  cardDrawerStore.open(nodeId, tab);
}
export function closeCardDrawer(): void {
  cardDrawerStore.close();
}
