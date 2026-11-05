/** Části velínu AGI Pletor v pořadí z kontraktu (§3); `ready` = od V1 funkční, ostatní jsou zatím jen místo na milník. */
export const PARTS = [
  { id: "prehled", label: "Přehled", ready: true },
  { id: "mozek", label: "Mozek a LLM", ready: true },
  { id: "hlas", label: "Hlas", ready: true },
  { id: "srdce", label: "Srdce", ready: false, milestone: "V2" },
  { id: "podklady", label: "Podklady", ready: false, milestone: "V2" },
  { id: "dilna", label: "Dílna", ready: true },
  { id: "monitoring", label: "Monitoring", ready: false, milestone: "V3" },
  { id: "rozhovor", label: "Rozhovor", ready: false, milestone: "V3" },
  { id: "nastaveni", label: "Nastavení", ready: false, milestone: "V4" },
] as const;

export type PartId = (typeof PARTS)[number]["id"];
export const DEFAULT_PART: PartId = "prehled";

/** Část z `?part=`; chybějící nebo neznámá hodnota je Přehled. */
export function parsePart(search: string): PartId {
  const value = new URLSearchParams(search).get("part");
  return PARTS.find((part) => part.id === value)?.id ?? DEFAULT_PART;
}

/** Je adresa stránkou velínu (`?screen=pletor`)? */
export const isDashboardRoute = (search: string) => new URLSearchParams(search).get("screen") === "pletor";

/** Adresa velínu s danou částí; ostatní parametry (projekt, prostor) zůstanou. */
export function withPart(search: string, part: PartId): string {
  const q = new URLSearchParams(search);
  q.set("screen", "pletor");
  q.set("part", part);
  return "/?" + q;
}
