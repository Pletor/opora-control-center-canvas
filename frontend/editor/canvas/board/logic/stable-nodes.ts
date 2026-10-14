// Stabilní uzly plátna (docs/navrhy/2026-10-14-vykon-platna.md, oprava 3). Board při každé přestavbě
// postaví uzly vrstvy znovu, ale React Flow i `memo(NodeCard)` přeskočí kartu jen tehdy, když dostanou
// tentýž objekt. `reuseNodes` proto vrátí předchozí objekt uzlu, kdykoli se jeho vlastní výřez dat
// nezměnil (hluboká shoda), a nově postavenému uzlu přenese `measured`, `width` a `height` z předchozí
// verze: bez nich React Flow kartu do přeměření skryje a rozepsaná textarea v ní ztratí fokus.
import type { Node } from "@xyflow/react";

/** Hluboká shoda čistých dat (pole, prosté objekty, primitiva); funkce a jiné objekty jen podle reference. */
export function sameValue(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) return false;
  if (Array.isArray(a)) {
    if (!Array.isArray(b) || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (!sameValue(a[i], b[i])) return false;
    return true;
  }
  if (Array.isArray(b)) return false;
  const protoA = Object.getPrototypeOf(a);
  if (protoA !== Object.getPrototypeOf(b) || (protoA !== Object.prototype && protoA !== null)) return false;
  const left = a as Record<string, unknown>;
  const right = b as Record<string, unknown>;
  let count = 0;
  for (const key in left) {
    if (!Object.prototype.hasOwnProperty.call(left, key)) continue;
    count++;
    if (!Object.prototype.hasOwnProperty.call(right, key) || !sameValue(left[key], right[key])) return false;
  }
  for (const key in right) if (Object.prototype.hasOwnProperty.call(right, key)) count--;
  return count === 0;
}

/** Klíče, které se porovnávají zvlášť: data hluboce, rozměry podle toho, jestli je builder nastavil. */
const SEPARATE = new Set(["data", "measured", "width", "height"]);

/**
 * Stejná slupka: každý vlastní klíč obou uzlů kromě `data`, `measured`, `width` a `height` se shoduje
 * (hluboce, takže nově postavený `style` se stejnými čísly projde), výslovné `width` / `height` z nové
 * verze se shodují se starými a `data` jsou hluboce stejná. Klíč, který si do starého uzlu dopsal React
 * Flow (např. `dragging`), shodu zruší; uzel se pak jednou postaví znovu.
 */
export function sameShell(previous: Node, next: Node): boolean {
  const a = previous as unknown as Record<string, unknown>;
  const b = next as unknown as Record<string, unknown>;
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (SEPARATE.has(key)) continue;
    if (!sameValue(a[key], b[key])) return false;
  }
  if (next.width !== undefined && next.width !== previous.width) return false;
  if (next.height !== undefined && next.height !== previous.height) return false;
  return sameValue(previous.data, next.data);
}

/**
 * Nové pole uzlů, ve kterém nezměněné karty drží svou starou referenci. Pořadí a obsah určuje `built`;
 * z `previous` se bere jen identita (beze změny) nebo naměřené rozměry (změněná karta).
 */
export function reuseNodes(previous: readonly Node[], built: readonly Node[]): Node[] {
  const before = new Map<string, Node>();
  for (const node of previous) before.set(node.id, node);
  return built.map((node) => {
    const old = before.get(node.id);
    if (!old) return node;
    if (sameShell(old, node)) return old;
    // Změřený rozměr patří jen stejnému druhu uzlu; výslovné rozměry nové verze mají přednost.
    return old.measured && old.type === node.type
      ? { ...node, measured: old.measured, width: node.width ?? old.width, height: node.height ?? old.height }
      : node;
  });
}

/** Kolik uzlů dostalo nový objekt (a React Flow je tedy překreslí); pro testy a měření. */
export const changedNodes = (previous: readonly Node[], next: readonly Node[]): string[] => {
  const before = new Map(previous.map((node) => [node.id, node]));
  return next.filter((node) => before.get(node.id) !== node).map((node) => node.id);
};
