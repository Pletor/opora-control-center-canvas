// Rodič Profil projektu v šuplíku: skládá hlavičku projektu a pod ní kartu profilu. Karta je
// rozbalená sama, dokud profil není nastavený a uživatel ji neodložil („Teď ne“), nebo když ji
// otevře odkaz „Změnit“. Nic nenačítá ani neukládá — profil, stav ukládání i chybu dostane v props
// a každou volbu hlásí nahoru; ukládá App.
import ProjectHead from "@/layout/project-profile/components/ProjectHead";
import ProfileCard from "@/layout/project-profile/components/ProfileCard";
import { profileUnset, type ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { profileWords } from "@/shared/project-capabilities/logic/project-profile";
import type { ProfileDraft } from "@/layout/project-profile/logic/profile-card";
import "@/layout/project-profile/styles/project-profile.css";

export default function ProjectProfile({
  name,
  profile,
  loaded,
  editing,
  dismissed,
  saving,
  error,
  onEdit,
  onDismiss,
  onSave,
  onReload,
}: {
  name: string;
  profile: ProjectProfile;
  /** Nastavení už dorazilo; do té doby se karta neukazuje, aby neblikla u nastaveného projektu. */
  loaded: boolean;
  editing: boolean;
  dismissed: boolean;
  saving: boolean;
  error: string;
  onEdit: (editing: boolean) => void;
  onDismiss: () => void;
  onSave: (draft: ProfileDraft) => void;
  onReload: () => void;
}) {
  const unset = profileUnset(profile);
  const open = editing || (loaded && unset && !dismissed);
  return (
    <>
      <ProjectHead name={name} words={profileWords(profile)} unset={unset} open={open} onEdit={() => (open ? onDismiss() : onEdit(true))} />
      {open ? (
        <ProfileCard
          name={name}
          profile={profile}
          saving={saving}
          error={error}
          dismissLabel={unset ? "Teď ne, ukázat vše" : "Zrušit"}
          onSave={onSave}
          onDismiss={onDismiss}
          onReload={onReload}
        />
      ) : (
        error && <p className="project-profile__error" role="alert">{error}</p>
      )}
    </>
  );
}
