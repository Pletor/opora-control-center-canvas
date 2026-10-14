// Dílek Karta profilu: dvě otázky o projektu (architektura a uživatelé) a „Uložit pro projekt“.
// Stojí vždy rozbalená v sekci Nastavení menu; „Vrátit“ zahodí rozepsanou volbu. Rozepsaná volba žije jen v kartě, dokud ji uživatel neuloží; hotovou
// volbu hlásí `onSave` nahoru a ukládá rodič (App) přes /api/project-settings. Chybu ze serveru
// (například že se nastavení mezitím změnilo jinde) dostane hotovou a ukáže ji česky v kartě.
import { useEffect, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { ARCHITECTURE_OPTIONS, TENANCY_OPTIONS } from "@/shared/project-capabilities/logic/project-profile";
import { chooseArchitecture, chooseTenancy, draftChanged, draftOf, type ProfileDraft } from "@/layout/project-profile/logic/profile-card";
import "@/layout/project-profile/styles/project-profile.css";

export default function ProfileCard({
  name,
  profile,
  saving,
  error,
  onSave,
  onReload,
}: {
  name: string;
  profile: ProjectProfile;
  saving: boolean;
  error: string;
  onSave: (draft: ProfileDraft) => void;
  /** Po chybě: načíst uložené nastavení znovu. */
  onReload: () => void;
}) {
  const [draft, setDraft] = useState<ProfileDraft>(() => draftOf(profile));
  useScopedSaveParticipant({ id: "project-profile", label: "Profil projektu",
    dirty: draftChanged(draft, profile), pending: saving,
    blocked: "Změnu společného profilu potvrďte tlačítkem Uložit pro projekt nebo ji vraťte." });
  // Uložený profil se změnil (uložení, jiný projekt): karta začne od něj.
  useEffect(() => { setDraft(draftOf(profile)); }, [profile.architecture, profile.tenancy]);

  return (
    <section className="project-profile__card" aria-label="Profil projektu" data-testid="profile-card">
      <div>
        <p className="project-profile__question">Jaký je projekt {name || "tento projekt"}?</p>
        <p className="project-profile__intro">
          Dvě odpovědi stačí. Profil popisuje projekt pro celou aplikaci a ukládá se k projektu.
        </p>
      </div>
      <fieldset className="project-profile__group">
        <legend className="project-profile__legend">Architektura</legend>
        <div className="project-profile__pair">
        {ARCHITECTURE_OPTIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            className={"project-profile__option" + (draft.architecture === option.id ? " project-profile__option--on" : "")}
            aria-pressed={draft.architecture === option.id}
            disabled={saving}
            data-testid={"profile-architecture-" + option.id}
            onClick={() => setDraft(chooseArchitecture(draft, option.id))}
          >
            <span className="project-profile__option-label">{option.label}</span>
            <span className="project-profile__option-hint">{option.hint}</span>
          </button>
        ))}
        </div>
      </fieldset>
      <fieldset className="project-profile__group">
        <legend className="project-profile__legend">Uživatelé</legend>
        <div className="project-profile__pair">
          {TENANCY_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              className={"project-profile__option" + (draft.tenancy === option.id ? " project-profile__option--on" : "")}
              aria-pressed={draft.tenancy === option.id}
              disabled={saving}
              data-testid={"profile-tenancy-" + option.id}
              onClick={() => setDraft(chooseTenancy(draft, option.id))}
            >
              <span className="project-profile__option-label">{option.label}</span>
              <span className="project-profile__option-hint">{option.hint}</span>
            </button>
          ))}
        </div>
      </fieldset>
      {error && (
        <div className="project-profile__error" role="alert">
          <span>{error}</span>
          <button type="button" className="project-profile__link" onClick={onReload}>Načíst znovu</button>
        </div>
      )}
      <div className="project-profile__actions">
        <button
          type="button"
          className="project-profile__save"
          disabled={saving || !draftChanged(draft, profile)}
          data-testid="profile-save"
          onClick={() => onSave(draft)}
        >
          {saving ? "Ukládám…" : "Uložit pro projekt"}
        </button>
        {draftChanged(draft, profile) && (
          <button type="button" className="project-profile__dismiss" disabled={saving} data-testid="profile-dismiss" onClick={() => setDraft(draftOf(profile))}>
            Vrátit
          </button>
        )}
      </div>
      <p className="project-profile__note">Změníte ho kdykoli tady nebo v Nastavení → Projekt. Profil patří projektu, vzhled menu ne.</p>
    </section>
  );
}
