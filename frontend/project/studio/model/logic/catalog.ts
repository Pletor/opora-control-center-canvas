// Katalog typů komponent Studia: 68 typů a 227 portů (technologické + cloudové + obecné), pořadí jako v prototypu
// `catalog.mjs`. Data leží v samostatných modulech `catalog-*.ts`, aby se celý MODEL mohl načíst líně (`import()`).
import { baseCatalog } from "./catalog-base";
import { cloudCatalog } from "./catalog-cloud";
import { technologyCatalog } from "./catalog-technology";
import type { ComponentType, PortDirection, PortType } from "./model-types";

export const catalog: readonly ComponentType[] = [...technologyCatalog, ...cloudCatalog, ...baseCatalog];

const byId = new Map(catalog.map((type) => [type.id, type]));

export const componentType = (id: string): ComponentType | undefined => byId.get(id);

/** Pozorovaná barva tečky portu; u obecných požadavků a dat rozhoduje směr. Bez směru = místní konvence hrany a legendy. */
export function portColor(type: PortType, direction?: PortDirection): string {
  if (type === "sql-query" || type === "sql-result") return "#a88dff";
  if (type === "event" || type === "job") return "#f5b041";
  if (type === "telemetry" || type === "health") return "#ff78c8";
  if (type === "cache-command") return "#38d996";
  return direction === "output" ? "#38d996" : "#49b8ff";
}
