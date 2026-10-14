// Dílek Nastavení menu: karta profilu projektu (dostane ji hotovou v `profileCard`, vždy rozbalenou).
// Profil patří projektu a ukládá ho rodič (App) s očekávanou revizí; dílek jen skládá.
import type { ReactNode } from "react";

export default function DockSettings({ profileCard }: { profileCard: ReactNode }) {
  return (
    <div className="dock-settings" data-testid="dock-settings">
      <section className="dock-settings__group" aria-label="Profil projektu">
        <h3 className="dock-settings__heading">Profil projektu</h3>
        {profileCard}
      </section>
    </div>
  );
}
