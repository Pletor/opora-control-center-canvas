Profil projektu v menu Editoru (`docs/suplik-a-profil.md`, části 1 a 4; `docs/menu-a-katalog.md`, část A): hlavička projektu v Knihovně, Agentech a Postupech a karta profilu v Nastavení. Profil patří projektu (ukládá se do `/api/project-settings`), vzhled a ovládání šuplíku ne.

**Dílky**

- `components/ProjectProfile.tsx` — hlavička pro Knihovnu, Agenty a Postupy (a chyba ze serveru pod ní). Karta se tu nikdy nerozbaluje; odkaz hlásí `onSettings` a App přepne do sekce Nastavení. Nic nenačítá ani neukládá.
- `components/ProjectHead.tsx` — jméno projektu a pod ním řádek profilu s odkazem na konci: „Web · Modulární monolit · Změnit“, nebo „Profil nenastaven · Nastavit“ (`data-testid="project-profile-edit"`).
- `components/ProfileCard.tsx` — v sekci Nastavení vždy rozbalená (skládá ji App do `DockSettings`): dvě skupiny voleb (architektura, uživatelé) s krátkým popisem, „Uložit pro projekt“ (`profile-save`) a „Vrátit“ (`profile-dismiss`, jen když je rozepsaná změna). Rozepsaná volba žije v kartě, hotovou hlásí `onSave`. Chybu ze serveru (např. „Nastavení se změnilo v jiném okně. Obnovte je.“) ukáže česky s tlačítkem „Načíst znovu“.

**Logika**

- `logic/profile-card.ts` (+ test) — rozepsaná volba: `draftOf`, `chooseArchitecture`, `chooseTenancy` (druhý klik volbu zruší), `draftChanged`.
- `logic/use-project-profile.ts` — jen pro App: načte `/api/project-settings` pro otevřený projekt (znovu při otevření sekce menu) a `save(draft)` pošle celé nastavení s `expected_revision`. Chyba zůstane v `error`, `reload()` načte uložené nastavení znovu.

**Styl**

`styles/project-profile.css`, blok `project-profile`, BEM s příběhovými komentáři, barvy jen z tokenů (světlý i tmavý režim).
