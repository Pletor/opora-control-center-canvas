// Rodič Profil projektu v menu: hlavička projektu pro Knihovnu, Agenty a Postupy. Karta profilu se
// tu nerozbaluje — odkaz „Nastavit“ / „Změnit“ hlásí `onSettings` a rodič přepne do sekce Nastavení,
// kde karta stojí vždy rozbalená. Nic nenačítá ani neukládá; chybu ze serveru dostane hotovou.
import ProjectHead from "@/layout/project-profile/components/ProjectHead";
import { profileUnset, type ProjectProfile as Profile } from "@/shared/project-capabilities/logic/project-capabilities";
import { profileWords } from "@/shared/project-capabilities/logic/project-profile";
import "@/layout/project-profile/styles/project-profile.css";

export default function ProjectProfile({
  name,
  profile,
  loaded,
  error,
  onSettings,
}: {
  name: string;
  profile: Profile;
  /** Nastavení už dorazilo; do té doby hlavička neříká „nenastaven“, aby to neblikalo u nastaveného projektu. */
  loaded: boolean;
  error: string;
  onSettings: () => void;
}) {
  return (
    <>
      <ProjectHead name={name} words={loaded ? profileWords(profile) : "Načítám profil…"} unset={loaded && profileUnset(profile)} onSettings={onSettings} />
      {error && <p className="project-profile__error" role="alert">{error}</p>}
    </>
  );
}
