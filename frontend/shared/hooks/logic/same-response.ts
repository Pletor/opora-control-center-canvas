// Polling bez prázdných přestaveb (docs/navrhy/2026-10-14-vykon-platna.md, oprava 6): odpověď, která
// se od minula nezměnila, nesmí vyrobit nový objekt, jinak React překreslí Board a všechny karty,
// i když se nic neděje. `keepSame` vrací původní referenci, když je nový obsah stejný.

/** Hluboká shoda přes JSON; odpovědi API jsou čisté JSON, takže pořadí klíčů je stabilní (stejný server). */
export function sameJson(a: unknown, b: unknown): boolean {
  return a === b || JSON.stringify(a) === JSON.stringify(b);
}

/** Starý objekt, když je nový stejný; jinak nový. Určeno pro `setState((current) => keepSame(current, next))`. */
export function keepSame<T>(current: T, next: T): T {
  return sameJson(current, next) ? current : next;
}
