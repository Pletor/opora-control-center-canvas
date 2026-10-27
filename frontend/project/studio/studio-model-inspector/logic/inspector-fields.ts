// Pole inspektoru MODELu: parametry simulace komponenty (`config.model`) podle `parameterKeys` typu s popiskem a mezemi
// z tabulky `parameters` (u partitioned-store jeho vlastní tabulka), zadaná hodnota a výchozí hodnota jako nápověda.
// Zápis pole se ověří stejnou kontrolou jako uložení (`validateModelConfig`: meze, celá čísla, profil), takže chyba
// se ukáže hned u pole a do modelu se nedostane. Čistá logika bez Reactu.
import type { StudioModelNode } from "../../model/logic/model-types";
import { cloudProfile } from "../../model/simulation/logic/cloud-profiles";
import { partitionedParameters } from "../../model/simulation/logic/partitioned-model";
import { config, parameterKeys, parameters, validateModelConfig } from "../../model/simulation/logic/simulation-config";
import type { ParameterRule } from "../../model/simulation/logic/simulation-types";

export type ParameterRow = { key: string; label: string; min?: number; max?: number; step?: number; options?: readonly string[];
  value: number | string | undefined; fallback: string };

const ruleOf = (type: string, key: string): ParameterRule | undefined =>
  (cloudProfile(type) === "partitioned-store" ? partitionedParameters[key] : undefined) ?? parameters[key];

const shown = (value: unknown) => value === undefined || value === null ? "" : String(value);

export function parameterRows(node: Pick<StudioModelNode, "type" | "config">): ParameterRow[] {
  const given = (node.config.model ?? {}) as Record<string, number | string>, effective = config(node);
  return parameterKeys(node.type).flatMap((key) => {
    const rule = ruleOf(node.type, key);
    if (!rule) return [];
    return [{ key, label: rule.label, min: rule.min, max: rule.max, step: rule.step, options: rule.enum, value: given[key], fallback: shown(effective[key]) }];
  });
}

export type ParsedParameter = { value: number | string | undefined } | { error: string };

/** Text pole → hodnota parametru; prázdné pole = výchozí hodnota (undefined). Desetinná čárka se bere jako tečka. */
export function parseParameter(node: Pick<StudioModelNode, "type" | "config">, row: Pick<ParameterRow, "key" | "options">, raw: string): ParsedParameter {
  const text = raw.trim();
  if (!text) return { value: undefined };
  const value = row.options ? text : Number(text.replace(",", "."));
  if (typeof value === "number" && !Number.isFinite(value)) return { error: "Zadejte číslo." };
  try {
    validateModelConfig({ ...(node.config.model as Record<string, unknown> | undefined ?? {}), [row.key]: value }, node.type);
    return { value };
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}
