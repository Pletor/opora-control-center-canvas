// Podmíněné GET (karta P3): server u stavu, grafu, indexu a výpisu verzí posílá ETag. Klient si
// k URL pamatuje poslední ETag a surové tělo, další dotaz pošle s If-None-Match a odpověď 304
// (beze změny, bez těla) obslouží z paměti. Prohlížeč nic neukládá (server posílá no-store), proto
// hlavičku posíláme výslovně. Drží se jen odpovědi s ETagem; paměť má strop a nejstarší URL vypadne.

/** Kolik různých URL si klient pamatuje (každý projekt, prostor a dotaz indexu je jiné URL). */
export const ETAG_CACHE_LIMIT = 32;

export type EtagEntry = { etag: string; raw: string };

export type EtagCache = {
  /** Hlavičky podmíněného dotazu pro URL; prázdné, když o URL nic nevíme. */
  headers: (url: string) => Record<string, string>;
  /** Zapamatuje tělo úspěšné odpovědi s ETagem; odpověď bez ETagu URL zapomene. */
  remember: (url: string, etag: string | null, raw: string) => void;
  /** Tělo pro 304; null = o URL nic nevíme (dotaz se zopakuje bez podmínky). */
  cached: (url: string) => string | null;
  size: () => number;
};

export function createEtagCache(limit = ETAG_CACHE_LIMIT): EtagCache {
  const entries = new Map<string, EtagEntry>();
  return {
    headers(url): Record<string, string> {
      const entry = entries.get(url);
      return entry ? { "If-None-Match": entry.etag } : {};
    },
    remember(url, etag, raw) {
      entries.delete(url);
      if (!etag) return;
      entries.set(url, { etag, raw });
      while (entries.size > limit) entries.delete(entries.keys().next().value as string);
    },
    cached(url) {
      const entry = entries.get(url);
      if (!entry) return null;
      // Nedávno použité URL jde na konec, ať při stropu vypadne to nejstarší.
      entries.delete(url);
      entries.set(url, entry);
      return entry.raw;
    },
    size: () => entries.size,
  };
}

/**
 * Tělo odpovědi 304: obsah se nezměnil, ale „kdy pozorováno“ (`observedAt`, `/api/view`) je teď.
 * Vrací nový objekt z uloženého textu, takže volající nesdílí objekt s pamětí klienta.
 */
export function notModifiedValue(raw: string, now: () => string = () => new Date().toISOString()): unknown {
  const value = JSON.parse(raw) as unknown;
  if (value && typeof value === "object" && !Array.isArray(value) && typeof (value as { observedAt?: unknown }).observedAt === "string")
    (value as { observedAt: string }).observedAt = now();
  return value;
}
