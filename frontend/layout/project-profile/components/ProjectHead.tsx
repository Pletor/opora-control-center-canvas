// Dílek Hlavička projektu: v šuplíku pod přepínačem Knihovna | Agenti stojí jméno projektu a jeho
// profil slovy („Web · Modulární monolit · Multitenant“) s odkazem „Změnit“. Uživatel tak vidí, ke
// kterému projektu výběr patří a podle čeho je zúžený. Text dostane hotový; klik hlásí nahoru.
export default function ProjectHead({
  name,
  words,
  unset,
  open,
  onEdit,
}: {
  name: string;
  words: string;
  /** Profil nenastavený: odkaz zve k nastavení místo ke změně. */
  unset: boolean;
  /** Karta profilu je rozbalená pod hlavičkou; odkaz ji pak sbalí. */
  open: boolean;
  onEdit: () => void;
}) {
  return (
    <div className="project-profile" data-testid="project-head">
      <div className="project-profile__text">
        <strong className="project-profile__name">{name || "Projekt"}</strong>
        <span className="project-profile__words">{words}</span>
      </div>
      <button
        type="button"
        className="project-profile__link"
        aria-expanded={open}
        data-testid="project-profile-edit"
        onClick={onEdit}
      >
        {open ? "Zavřít" : unset ? "Nastavit" : "Změnit"}
      </button>
    </div>
  );
}
