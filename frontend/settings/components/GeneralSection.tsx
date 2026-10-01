import { useCallback, useEffect, useRef, useState } from "react";
import { setAppearance, useDesktopAppearance, type DesktopDensity, type DesktopTheme } from "@/app/logic/desktop-appearance";
import MapRefreshSetting from "@/settings/components/MapRefreshSetting";
import { mapRefreshPayload, parseMapRefreshConfig, type MapRefreshConfig } from "@/settings/logic/map-refresh-config";
import { api } from "@/shared/types/logic/types";

const THEMES: { id: DesktopTheme; label: string }[] = [
  { id: "light", label: "Světlý" },
  { id: "dark", label: "Tmavý" },
];
const DENSITIES: { id: DesktopDensity; label: string }[] = [
  { id: "compact", label: "Kompaktní" },
  { id: "normal", label: "Běžná" },
  { id: "airy", label: "Vzdušná" },
];

/**
 * Obecné: vzhled rozhraní (jen v tomto prohlížeči) a automatická aktualizace map (na serveru,
 * pro celou aplikaci). Automatiku ukládá tato sekce: po přepnutí stav znovu přečte ze serveru.
 */
export default function GeneralSection() {
  const appearance = useDesktopAppearance();
  const [mapRefresh, setMapRefresh] = useState<MapRefreshConfig | null>(null);
  const [mapRefreshError, setMapRefreshError] = useState("");
  const [savingMapRefresh, setSavingMapRefresh] = useState(false);
  const generation = useRef(0);

  const readMapRefresh = useCallback(async () => {
    const ticket = ++generation.current;
    try {
      const value = parseMapRefreshConfig(await api<unknown>("/api/map-refresh/config"));
      if (ticket !== generation.current) return;
      setMapRefresh(value);
      setMapRefreshError(value ? "" : "Server vrátil neznámý stav automatiky map.");
    } catch (reason) {
      if (ticket !== generation.current) return;
      setMapRefresh(null);
      setMapRefreshError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void readMapRefresh();
    return () => { ++generation.current; };
  }, [readMapRefresh]);

  async function changeMapRefresh(enabled: boolean) {
    if (savingMapRefresh) return;
    setSavingMapRefresh(true);
    try {
      await api<MapRefreshConfig>("/api/map-refresh/configure", mapRefreshPayload(enabled));
      await readMapRefresh();
    } catch (reason) {
      setMapRefreshError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSavingMapRefresh(false);
    }
  }

  return (
    <section className="settings-section" aria-labelledby="general-title">
      <h3 id="general-title">Obecné</h3>
      <p className="muted">Vzhled je preference tohoto prohlížeče. Automatika map platí pro celou aplikaci.</p>
      <div className="settings-row">
        <span>Barevný režim</span>
        <div className="v3-segment">
          {THEMES.map((item) => (
            <button type="button" key={item.id} aria-pressed={appearance.theme === item.id} onClick={() => setAppearance({ theme: item.id })}>
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="settings-row">
        <span>Hustota</span>
        <div className="v3-segment">
          {DENSITIES.map((item) => (
            <button type="button" key={item.id} aria-pressed={appearance.density === item.id} onClick={() => setAppearance({ density: item.id })}>
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <MapRefreshSetting config={mapRefresh} saving={savingMapRefresh} error={mapRefreshError} onChange={(enabled) => void changeMapRefresh(enabled)} />
    </section>
  );
}
