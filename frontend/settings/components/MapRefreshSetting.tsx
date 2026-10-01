import { mapRefreshView, type MapRefreshConfig } from "@/settings/logic/map-refresh-config";

/**
 * Řádek „Automatická aktualizace map po mergi do main“. Dostává stav ze serveru v props a každou
 * změnu hlásí nahoru; ukládá rodič (GeneralSection). Nastavení platí pro celou aplikaci.
 */
export default function MapRefreshSetting({ config, saving, error, onChange }: {
  config: MapRefreshConfig | null;
  saving: boolean;
  error: string;
  onChange: (enabled: boolean) => void;
}) {
  const view = mapRefreshView(config);
  return (
    <div className="map-refresh-setting">
      <label className="map-refresh-setting__row">
        <span className="map-refresh-setting__label">Automatická aktualizace map po mergi do main</span>
        <input
          className="map-refresh-setting__switch"
          type="checkbox"
          checked={view.checked}
          disabled={view.busy || saving}
          onChange={(event) => onChange(event.target.checked)}
        />
      </label>
      <span className="map-refresh-setting__detail">{view.detail}</span>
      {error && <span className="map-refresh-setting__error" role="alert">{error}</span>}
    </div>
  );
}
