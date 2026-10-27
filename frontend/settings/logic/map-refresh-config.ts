/**
 * Globální přepínač automatické aktualizace map (docs/mapy-projektu.md).
 *
 * Platí pro celou aplikaci, nikdy pro jeden projekt. Stav se čte z `GET /api/map-refresh/config`
 * a mění přes `POST /api/map-refresh/configure {enabled}`; v rozhraní stojí vždy odpověď serveru.
 */
export type MapRefreshConfig = { enabled: boolean };

/** Co ukáže řádek v Nastavení → Obecné. */
export type MapRefreshView = {
  /** Poloha přepínače; `false`, dokud se stav nepřečte. */
  checked: boolean;
  /** Dokud se stav nepřečetl, nemá se čím přepínat. */
  busy: boolean;
  /** Jedna věta o tom, co přepínač právě znamená. */
  detail: string;
};

/** Odpověď serveru; cizí tvar se čte jako „neznámý stav“, ne jako vypnuto. */
export function parseMapRefreshConfig(value: unknown): MapRefreshConfig | null {
  if (!value || typeof value !== "object") return null;
  const enabled = (value as { enabled?: unknown }).enabled;
  return typeof enabled === "boolean" ? { enabled } : null;
}

export function mapRefreshView(config: MapRefreshConfig | null): MapRefreshView {
  if (!config) return { checked: false, busy: true, detail: "Zjišťuji stav automatiky…" };
  return config.enabled
    ? { checked: true, busy: false, detail: "Po každém mergi do main se Graphify přepíše na místě ve všech projektech." }
    : { checked: false, busy: false, detail: "Mapy se aktualizují jen volbou „Aktualizovat teď“ v mapě projektu." };
}

/** Tělo přepnutí; server přijme právě jedno pole a nic navíc. */
export function mapRefreshPayload(enabled: boolean): MapRefreshConfig {
  return { enabled };
}
