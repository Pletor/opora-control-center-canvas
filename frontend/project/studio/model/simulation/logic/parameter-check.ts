// Společná kontrola parametrů kernelů (`valid(c)` v prototypových `*-model.mjs`): výčet, konečné číslo v mezích,
// celé číslo u celočíselných klíčů. Chyba je `RangeError` se jménem kernelu a klíče, stejně jako v prototypu.
import type { ModelConfig, ParameterTable } from "./simulation-types";

export function checkParameters(c: ModelConfig, table: ParameterTable, integers: readonly string[], kernel: string): void {
  for (const [key, rule] of Object.entries(table)) {
    const value = c[key];
    if (rule.enum) {
      if (!rule.enum.includes(value)) throw new RangeError(`Invalid ${kernel} parameter: ${key}`);
    } else if (!Number.isFinite(value) || value < rule.min! || value > rule.max! || (integers.includes(key) && !Number.isInteger(value)))
      throw new RangeError(`Invalid ${kernel} parameter: ${key}`);
  }
}

/** Kapacitní činitel incidentu Slow (1 = plný výkon, 0,2 = pětkrát pomalejší). */
export function checkCapacityFactor(capacityFactor: number, kernel: string): void {
  if (!Number.isFinite(capacityFactor) || capacityFactor < 0 || capacityFactor > 1) throw new RangeError(`Invalid ${kernel} capacity factor`);
}

export type KernelOptions = { capacityFactor?: number; failed?: boolean };
