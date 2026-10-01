// Dílek Hlavička projektu: v Knihovně, Agentech a Postupech stojí pod názvem sekce jméno projektu
// a pod ním profil slovy („Web · Modulární monolit · Multitenant · Změnit“). Když profil chybí,
// řádek zní „Profil nenastaven · Nastavit“. Karta profilu se tu nikdy nerozbaluje — odkaz přepne
// do sekce Nastavení, kde karta bydlí. Text dostane hotový, klik hlásí nahoru.
export default function ProjectHead({
  name,
  words,
  unset,
  onSettings,
}: {
  name: string;
  words: string;
  /** Profil nenastavený: řádek zve k nastavení místo ke změně. */
  unset: boolean;
  onSettings: () => void;
}) {
  return (
    <div className="project-profile" data-testid="project-head">
      <div className="project-profile__text">
        <strong className="project-profile__name">{name || "Projekt"}</strong>
        <span className="project-profile__words" data-testid="project-profile-words">
          {unset ? "Profil nenastaven" : words} ·{" "}
          <button type="button" className="project-profile__link" data-testid="project-profile-edit" onClick={onSettings}>
            {unset ? "Nastavit" : "Změnit"}
          </button>
        </span>
      </div>
    </div>
  );
}
