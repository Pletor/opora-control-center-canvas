---
name: git-linie
agent: pletor
description: Použít při práci s větvemi, náhledem, přijetím nebo nasazením změn, nebo když se člověk ptá, kde pracujeme a co se smí sloučit kam.
---

# Git linie

## Úloha

Pletor drží přehled o větvích tématu a vysvětluje ho člověku. Sám nepřijímá změny za člověka, nezapisuje na plátno a hlídá, aby se do `develop` a `main` nic nedostalo bez přijetí ve Velínu. Zdroj pravdy: `docs/navrhy/2026-11-06-velin-git-linie.md`, pravidla stavby `docs/cista-linie.md`.

## Role větví

Strom větví (`docs/navrhy/2026-11-06-linie-strom-vetvi.md`). Role se odvozuje z názvu. Vztahy a přijetí eviduje Velín (část Linie), ne Git sám.

```
main                          produkce
└─ develop                    čisté věci z vývoje, poslední filtr před main
   ├─ items/<díl>             univerzální komponenta; do develop nebo do feat větve, která ji potřebuje
   └─ feat/velin              kořen komponenty
      └─ feat/velin-linie        hlavní struktura
         ├─ feat/velin-linie-vodotisk   dílčí věc
         └─ feat/velin-linie-strom      dílčí věc
```

`fix/*`, `hotfix/*` (z nasazeného SHA do `main`, pak přenos do `develop`) a `experiment/*` (nikam automaticky) jako dosud.

Větev vzniká z rodiče podle jména (`feat/a-b` z `feat/a`, `feat/a` z `develop`) a slučuje se jen do rodiče. Kořen `feat/<a>` jde do `develop` až po poslední kontrole celé komponenty; `items/*` do `develop` nebo do feat větve, kde je díl potřeba. `develop -> main` a kořen feat `-> develop` merge commitem, squash jen u krátkých `feat/*` a `fix/*`. Vlak PR dál platí, `base` vagonu je rodič.

## Přijetí

- Přijetí zapisuje jen člověk ve Velínu, vždy pro konkrétní `{větev, SHA, cíl}`. Agent ho nikdy nezapíše ani nenahrazuje (routa vrací agentovi 403).
- Nový commit na větvi nebo jiný cíl znamená nové přijetí; staré je „zastaralé“.
- Do `develop` a `main` se slučuje jen s platným přijetím pro přesně tu hlavu a ten cíl.

## Kdy zastavit a hlásit

- V tématu jsou nepřijaté změny a chystá se postup do vyšší úrovně.
- Pro `develop` nebo `main` chybí platné přijetí.
- Nasazení by proběhlo bez zápisu nasazeného SHA.
- Chystá se přepsat sdílenou větev (`main`, `develop`, `items/*`, cizí `feat/*`).

Hlášení říká: která větev, jaké SHA, jaký cíl, co chybí.

## Náhled a nasazení

- Náhled se spouští z Velínu (část Linie) nad worktree větve, na vlastním portu a s kopií dat. Nikdy ne přes merge do `main` ani restartem 8740.
- Nasazení je samostatná akce po sloučení: ff pull, build, restart, ověření. Pak člověk zapíše nasazené SHA do Velínu. Merge sám nic nenasazuje.

## Nástroj v terminálu

- `uv run python tools/linie.py task` před editací: ověří, že jsi v repozitáři/worktree a na větvi úkolu; exit 2 = jiný kontext, nezačínej a nic nezahazuj.
- `uv run python tools/linie.py report --check "npm test=green"` po commitu a testech (pošle HEAD a kontroly); commit kuličku neuzavírá.
- `uv run python tools/linie.py merge` jen přes službu OPORY; 409 vypíše důvod. Přijetí za člověka nezapisuj. Exit 3 = evidence nedostupná, kód zachovej a hlas blokaci.

## Vodotisk

Každý commit úkolu nese trailer `Opora-Mark: OP-…` (značka je ve výpisu `linie task`). Komentář `# OP-….<krok>: proč` patří jen k podstatě kroku, ne k každé funkci. Před hlášením „hotovo“ spusť `uv run python tools/linie.py trace`. Stavy hran: `verified` je doloženo z Gitu a evidence, `claimed` je jen tvrzení agenta, `inferred` je odvozeno z větve bez značky, `missing` hrana chybí (pravdivý stav práce mimo proces).

## Git operace

- `develop -> main` a kořen feat `-> develop`: merge commit. Squash jen u krátkých `feat/*` a `fix/*`.
- Rebase (`--onto`, force-push s lease) jen na vlastní pracovní větev vlaku. Žádný force-push na sdílené větve.
- Žádný `reset --hard` ani `clean` jako úklid cizí práce; vyčisti jen to, co jsi sám vytvořil.
- Před změnou směru udělej kontrolní bod (commit nebo tag na větvi), ať je kam se vrátit.
- Revert kódu nevrací migrace ani data; u změn schématu to řekni předem.

## Organizace práce

Hlavní vlákno (Pletor, hlavní model) myslí a zadává: čte zadání, drží celek, rozděluje práci na nezávislé kusy. Implementaci, hledání v kódu a rutinu deleguje subagentům s přesným zadáním: kontrakt, seznam souborů, ověřovací příkazy, zákaz sahat mimo scope. Výsledek ověřuje testy a sestavením; hlášení „hotovo“ nikdy nepřebírá slepě.

## Co umět vysvětlit

Na dotaz odpověz: kde teď pracujeme (větev, rodič, cíl), proč tam, co člověk uvidí v náhledu, co chybí (přijetí, ověření, nasazení) a kam se změna může posunout dál.
