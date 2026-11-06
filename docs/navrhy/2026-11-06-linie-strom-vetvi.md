# Linie L5 – strom větví: pevné main / develop / items, dynamické feat zanořené podle jména

Datum: 2026-11-06. Nahrazuje §3 v `2026-11-06-velin-git-linie.md` (role topic/feat). Navazuje na L4 (`2026-11-06-linie-vodotisk-cesty.md`).

## Proč

Ploché role větví neříkají, kde se pracuje a pod kým. Člověk chce strom, ve kterém jméno větve nese cestu: komponenta →
její struktura → dílčí věc (tlačítko, stránka, logika). Dílčí věc se ladí zvlášť na své větvi, po přijetí se slučuje
**jen do rodiče**, a teprve hotový kořen komponenty jde po poslední kontrole do `develop`.

## Strom

```
main                              produkce
└─ develop                        čisté věci z vývoje, poslední filtr před main
   ├─ items/<díl>                 univerzální komponenta; slučuje se do develop nebo do feat větve, která ji potřebuje
   └─ feat/velin                  kořen komponenty (co je ve Velínu)
      └─ feat/velin-linie            hlavní struktura Linie
         ├─ feat/velin-linie-vodotisk  dílčí věc (L4)
         └─ feat/velin-linie-strom     dílčí věc (tento kontrakt)
```

Pevné větve: `main`, `develop`, `items/*`. Dynamické: `feat/*` zanořené podle jména; `fix/*`, `hotfix/*`, `experiment/*`
jako dosud.

## Pravidla (vynucuje backend, ne prompt)

1. **Rodič ze jména.** `feat/a-b-c` → nejdelší **existující** prefix na hranici `-` (`feat/a-b`, jinak `feat/a`);
   `feat/a` → `develop`; `items/x` → `develop`; `develop` → `main`; `hotfix/*` → `main`; `fix/*` a `experiment/*` →
   `baseBranch` z práce (jméno neurčuje). `feat/velinzzz` není dítě `feat/velin` (hranice `-` je povinná).
2. **Větev vzniká z rodiče.** `POST /work` bez `baseBranch` rodiče odvodí; s `baseBranch` ověří `is_child(branch, base)`,
   jinak 422 `branch_hierarchy` („feat/a-b vzniká z feat/a“). `baseSha` = HEAD rodiče v okamžiku založení.
3. **Slučuje se jen do rodiče.** `target` výchozí = rodič; jiný cíl → 422 `target_not_parent`. Výjimka `items/*`:
   do `develop`, nebo do feat větve, kterou člověk výslovně povolí v `allow-merge` (univerzální díl tam, kde je potřeba).
   `merge.py` totéž ověří těsně před operací (409). Kořen `feat/<a>` → `develop` až po poslední kontrole celé komponenty.
4. **Pořadí a hloubka.** `GET /` a `/board` nesou `parent` a `depth`; pořadí depth-first (main, develop, items/* abecedně,
   pak feat stromy: rodič před dětmi, sourozenci abecedně). Git graf i editor kreslí strom v tomto pořadí; editor řádky
   odsazuje podle hloubky.
5. **Role `topic` zaniká.** Staré řádky typu `topic` se čtou jako `items`.

## Datový model

- `tree.py` (čistý): `role(name)`, `parent(name, heads)`, `depth(name, heads)`, `order(heads)`, `is_child(branch, base)`.
- `rows.json`: `TYPES = items | work | experiment | fix`; žádné nové pole – rodič řádku se odvodí z `base.branch`.
- `work`: beze změny tvaru; `baseBranch`/`target` se doplní, když chybí.
- Odpovědi: `branches[].parent`, `branches[].depth`; `board.rows[].parent`, `board.rows[].depth`.

## Terminál a postupy

`linie task` vypíše „rodič: …; začlení se do: …“. Skill `git-linie(-srdce)`, seed `opora-control-center`, `CLAUDE.md`:
„Větev vzniká z rodiče podle jména (`feat/a-b` z `feat/a`) a vrací se jen do něj; kořen feat do develop po poslední
kontrole; `items/*` tam, kde je díl potřeba.“ `docs/cista-linie.md` §3 se mění stejně.

## Migrace (provedena 2026-11-06)

`feat/velin` z `develop@d8da63b`; `feat/linie-vodotisk` → `feat/velin-linie-vodotisk`; `topic/linie` smazána;
`feat/velin-linie` zůstává (rodič `feat/velin` odvozen jménem, shodný výchozí commit). Kuličky na 8740 v řádku „Velín“:
`feat/velin-linie` → `feat/velin`, `feat/velin-linie-vodotisk` → `feat/velin-linie`, `feat/velin-linie-strom` →
`feat/velin-linie-vodotisk`; staré kuličky s cílem `topic/linie` blokovány s důvodem.

## Ověření

- `uv run pytest backend/agi_pletor backend/api/agi_pletor tools -q`, `npm test`, `npm run build`.
- Testy: rodič ze jména včetně chybějícího mezičlánku a hranice `-`; `items/x` → `develop`; pořadí depth-first;
  `POST /work` bez `baseBranch`; špatný rodič 422; merge do ne-rodiče 409; board nese `depth`; formulář předvyplní rodiče.
- Živě: strom Velín → Linie → vodotisk/strom v editoru odsazený, Git graf v pořadí stromu.

## Mimo rozsah

Squash podle hloubky, GitHub rulesets, zakládání větví serverem, `items` → feat jako služba bez člověka.
