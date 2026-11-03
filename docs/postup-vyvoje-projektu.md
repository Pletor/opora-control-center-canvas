# Postup vývoje projektu přes OPORA

Návod pro každodenní práci: v OPORA píšeš zadání, ve VS Code ho plní agenti, kód jde na GitHub.
Příklad je Ample, ale stejně se pracuje s každým projektem.

## Kdo co drží

| Místo | Co tam je | Kdo tam píše |
|---|---|---|
| OPORA, `http://127.0.0.1:8740` | oblasti, sektory, uzly, zadání karet, stav a předávky agentů, mapy | ty, orchestrátor, agent jen přes API karty |
| Originální složka projektu ve VS Code (`I:\1. Projekty\01_ITNeskola\06_AmpleLab\ample`) | kód, testy, dokumentace kódu | agenti a ty |
| GitHub (`github.com/Pletor/ample`) | výsledek: commity a větve | push z VS Code |

Platí jedno pravidlo: **kód je v gitu, zadání a práce jsou v OPORA, nic není na obou místech.**
OPORA nikdy nepracuje v kopii. Projekt je připojený jako lokální složka na originál, žádný klon ani worktree.
Oba režimy v aplikaci existují a volí je druh projektu (`frontend/shared/project-capabilities/logic/project-capabilities.ts`): lokální projekt pracuje v originální složce jen ve workspace `draft`, git projekt má main jen ke čtení a pro uzel vlastní workspace (worktree). Tento postup používá lokální projekt.
Aplikace sama agenta nespustí ani nepushne. Agenty spouštíš ty.

## Jednou na začátku

1. **OPORA:** v kořeni repa Opory spusť `uv run opora`. Po každé změně Python kódu Opory ji restartuj.
2. **Projekt:** Ample je v OPORA připojený jako lokální projekt `ample`, id `cc5f34ec07cd455ca5ad1a69af19022b`, pracovní prostor `draft`. Další projekt připojíš na úvodní stránce projektů přes **Typ zdroje → Lokální složka**, kde zadáš originální cestu.
3. **Skill pro agenty:** `opora-control-center` je dostupný ve všech projektech přes odkaz `~/.claude/skills/opora-control-center`, který vede na generovanou kopii v repu Opory (aplikace ji při startu vygeneruje z Brainu, zdroj `backend/brain/seed/opora-control-center/`). Agent díky němu umí číst kartu a zapisovat výsledek.
4. **VS Code:** otevři originální složku projektu. Agenty pouštíš v integrovaném terminálu **v kořeni projektu**.

## Smyčka jednoho úkolu

### 1. Zadání v OPORA (Editor)

> Od 2026-10-15 platí pyramida (`pyramida.md`): člověk napíše **záměr oblasti**, agent-rozkladač navrhne sektory a karty
> jednou dávkou (tlačítka „Rozložit na sektory“ / „Rozložit na karty“ v inspektoru), člověk potvrdí dávku jedním rozhodnutím.
> Ruční vyplňování karty níže je stále možné, ale není nutné.

- Rozlož práci na **oblast → sektor → uzel**. Uzel je jedna doručitelná věc, kterou zvládne jeden agent.
- Na kartě uzlu vyplň:
  - **cíl**: co má po dokončení platit;
  - **mimo rozsah**: co agent dělat nesmí;
  - **akceptaci**: podle čeho poznáš hotovo;
  - **bloky splnění**: odškrtávací kritéria;
  - **pravidla** (`must` / `must_not`).
- Míří-li karta na existující kód, přidej **vazbu na cestu** (sourceRef). Podle ní se pak párují commity a hlídá rozsah.
- Kontrakt karty: [karta-pro-agenty.md](karta-pro-agenty.md).

### 2. Předání agentovi (VS Code)

Jeden terminál je jeden uzel. Agent kartu převezme akcí `claim` ze snímku agent-state (OporaHub); balíček karty ke čtení
dá v inspektoru **Načíst balíček karty** a stav práce ukazuje jednotný detail karty (dvojklik na kartu). Ručně vypadá takto – spusť `claude` v kořeni projektu a zadej:

```text
/opora-control-center
Projekt ample (cc5f34ec07cd455ca5ad1a69af19022b), workspace draft, uzel <ID uzlu>.
Načti node-brief (opora_read.py node-brief --project cc5f34ec07cd455ca5ad1a69af19022b --workspace draft --node <ID uzlu>), splň zadání podle pravidel tohoto repa (CLAUDE.md) a drž se rozsahu karty.
Commity piš s trailerem `Opora-Node: <ID uzlu>@<revize zadání>`.
Na konci zapiš do OPORA agent-output (stav bloků, návrh hotovo) a agent-workspace (log a předávka).
Nepushuj.
```

ID uzlu najdeš v detailu karty nebo v odkazu na ni.

**Řízená varianta (hooky):** s vybranou kartou otevři pravý panel **Agenti a postupy → Hook**, nastav povolené cesty a limity, vytvoř vazbu
a zkopírovaný příkaz `claude --session-id … --settings …` spusť v terminálu v kořeni projektu.
Agent pak dostane zadání hned při startu a OPORA hlídá, kam smí zapisovat a kolik nástrojů smí použít.
Použij ji u větších nebo paralelních úkolů.

### 3. Práce agenta

Agent se řídí pravidly projektu. U Ample to jsou orientace přes `brain-orientation`, u nové komponenty nejdřív `.drawio`,
testy vedle kódu a záznam do `docs/brain/pamet/kratka.md`. Výsledek hlásí do OPORA přes karty, ne do chatu.

### 4. Kontrola a uzavření (ty)

1. V OPORA projdi kartu: bloky, předávku, návrh „hotovo“. Pak hotovo potvrď, nebo kartu vrať s poznámkou.
2. V projektu ověř testy: u Ample `npm test` (a `npm run typecheck`).
3. Commity zkontroluj ve VS Code a pushni na GitHub. Ample má v CLAUDE.md pravidlo „push jen přes `git push no-mistakes`“.
   Remote `no-mistakes` ale zatím nemá, takže pushuješ na `origin`, dokud bránu nezřídíš.
4. Mapa (Graphify-out v prostředí Projekt) se obnoví po změně `main`. Hned je obnovíš přes **Aktualizovat graf → Aktualizovat teď**.
   Selže-li to, chyba ukáže důvod.

## Víc agentů najednou

- Každý agent má vlastní uzel a vlastní terminál.
- Uzly v jednom kole rozděl tak, aby se jejich cesty v kódu nepřekrývaly. Řízená varianta překrývající se cesty sama odmítne.
- Větve si dělá agent nebo ty ve VS Code. Bez worktree pracují všichni v jedné pracovní kopii, proto drž úkoly malé a nepřekrývající se.
- **Orchestrátor** je volitelná další relace Claude, třeba v repu Opory se stejným skillem. Čte plátno, rozkládá velké zadání na uzly
  a připravuje text karet. Agenty nespouští a nemerguje.
- Jak vznikají, slučují, nasazují a uklízí PR, když pracuje víc sessions naráz (ohlášení záměru, malé PR z čerstvého main bez řetězů, fronta slučování, nasazení server+klient, úklid vlastníkem): [cista-linie.md](cista-linie.md).

## Co když

| Vidíš | Znamená | Udělej |
|---|---|---|
| „Failed to fetch“ všude | backend neběží | `uv run opora` |
| Změna v kódu Opory se neprojevila | Python se za běhu nepřenačte | restart `uv run opora` |
| Agent nevidí skill | relace začala před vytvořením odkazu | nová relace `claude` |
| V `git status` projektu jsou `graphify-out/` nebo `graphify-out/opora-*` | výstupy map | OPORA je vylučuje přes `.git/info/exclude`, necommituj je |

## Záloha

Zadání z plátna leží jen na tomto PC v `.data/production/` repa Opory (mimo git).
Pravidelně tu složku kopíruj mimo disk, třeba před větší změnou. Kód je chráněný GitHubem, zadání jen touto zálohou.

## Vývoj samotné Opory

Opravy Opory dělej až při skutečném nedostatku a nejmenší změnou. Každá jde do vlastní větve nebo worktree
a do `main` až po `uv run pytest backend`, `npm test` a `npm run build`. Podrobná pravidla: [START-HERE.md](START-HERE.md), [pravidla-struktury.md](pravidla-struktury.md), linie PR a nasazení: [cista-linie.md](cista-linie.md).
