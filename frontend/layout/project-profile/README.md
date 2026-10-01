Profil projektu v šuplíku Knihovna/Agenti (`docs/suplik-a-profil.md`, části 1 a 4): hlavička projektu a karta profilu. Profil patří projektu (ukládá se do `/api/project-settings`), vzhled a ovládání šuplíku ne.

**Dílky**

- `components/ProjectProfile.tsx` — rodič: skládá hlavičku a pod ní kartu. Karta je otevřená, když profil není nastavený a uživatel ji neodložil, nebo když ji otevře odkaz „Změnit“. Nic nenačítá ani neukládá.
- `components/ProjectHead.tsx` — jméno projektu, profil slovy (`profileWords`: „Web · Modulární monolit · Multitenant“) a odkaz „Změnit“ / „Nastavit“ / „Zavřít“ (`data-testid="project-profile-edit"`).
- `components/ProfileCard.tsx` — dvě skupiny voleb (architektura, uživatelé) s krátkým popisem, „Uložit pro projekt“ (`profile-save`) a „Teď ne, ukázat vše“ / „Zrušit“ (`profile-dismiss`). Rozepsaná volba žije v kartě, hotovou hlásí `onSave`. Chybu ze serveru (např. „Nastavení se změnilo v jiném okně. Obnovte je.“) ukáže česky s tlačítkem „Načíst znovu“.

**Logika**

- `logic/profile-card.ts` (+ test) — rozepsaná volba: `draftOf`, `chooseArchitecture`, `chooseTenancy` (druhý klik volbu zruší), `draftChanged`.
- `logic/use-project-profile.ts` — jen pro App: načte `/api/project-settings` pro otevřený projekt (znovu při otevření šuplíku) a `save(draft)` pošle celé nastavení s `expected_revision`. Chyba zůstane v `error`, `reload()` načte uložené nastavení znovu.

**Styl**

`styles/project-profile.css`, blok `project-profile`, BEM s příběhovými komentáři, barvy jen z tokenů (světlý i tmavý režim).
