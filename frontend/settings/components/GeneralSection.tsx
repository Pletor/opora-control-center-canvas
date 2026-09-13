import { setAppearance, useDesktopAppearance, type DesktopDensity, type DesktopTheme } from "@/app/components/DesktopThemeControls";

const THEMES: { id: DesktopTheme; label: string }[] = [
  { id: "light", label: "Světlý" },
  { id: "dark", label: "Tmavý" },
];
const DENSITIES: { id: DesktopDensity; label: string }[] = [
  { id: "compact", label: "Kompaktní" },
  { id: "normal", label: "Běžná" },
  { id: "airy", label: "Vzdušná" },
];

/** Obecné: vzhled rozhraní. Ukládá se jen v tomto prohlížeči. */
export default function GeneralSection() {
  const appearance = useDesktopAppearance();
  return (
    <section className="settings-section" aria-labelledby="general-title">
      <h3 id="general-title">Obecné</h3>
      <p className="muted">Preference tohoto prohlížeče. Nemění projekt ani soubory.</p>
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
    </section>
  );
}
