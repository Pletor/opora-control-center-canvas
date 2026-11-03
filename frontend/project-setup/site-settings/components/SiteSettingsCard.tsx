import type { SiteSettings } from "@/shared/types/logic/types";
import { SITE_GROUPS, filledCount, siteValue, withSiteValue } from "@/project-setup/site-settings/logic/site-settings";
import "@/project-setup/site-settings/styles/site-settings.css";

/** Editor nastavení webu na stránce Projekt. Hodnoty dostává hotové, každou změnu hlásí `onChange`;
 *  ukládá rodič (ProjectHome) spolu s ostatním nastavením projektu a jeho revizí. */
export default function SiteSettingsCard({ site, disabled, onChange }: {
  site: SiteSettings; disabled: boolean; onChange: (site: SiteSettings) => void;
}) {
  return <fieldset className="site-settings" disabled={disabled}>
    <legend className="site-settings__title">Nastavení a design webu</legend>
    <p className="site-settings__intro">Platí pro celý web; srdce i agenti ho čtou ve snímku. Vyplňte jen to, co víte.</p>
    {SITE_GROUPS.map((group) => {
      const filled = filledCount(site, group);
      return <details key={group.id} className="site-settings__group" data-testid={`site-settings-${group.id}`}>
        <summary className="site-settings__summary">
          <span className="site-settings__name">{group.title}</span>
          <span className={filled ? "site-settings__count site-settings__count--filled" : "site-settings__count"}>{filled ? `vyplněno ${filled}/${group.fields.length}` : "nevyplněno"}</span>
        </summary>
        <p className="site-settings__hint">{group.hint}</p>
        <div className="site-settings__fields">
          {group.fields.map((field) => <label key={field.path} className="site-settings__field">
            <span className="site-settings__label">{field.label}</span>
            <input className="site-settings__input" aria-label={`${group.title}: ${field.label}`} maxLength={field.max}
              placeholder={field.placeholder} value={siteValue(site, field.path)}
              onChange={(event) => onChange(withSiteValue(site, field.path, event.target.value))} />
          </label>)}
        </div>
      </details>;
    })}
  </fieldset>;
}
