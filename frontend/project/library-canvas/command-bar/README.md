# Příkazový řádek plátna (`command-bar`)

Kontrakt `docs/navrhy/2026-11-04-platno-procesu.md` §1b. Zadání textem nad plátnem knihovny: srdce ho dostane jako zprávu člověka s kontextem plátna (`POST /api/brain/heart/messages`, `context: {kind: "flow", flowId, versionId, nodeIds}`), nakreslí do draftu a plátno ukáže `ProposalBar` (`../library-versions`).

- `components/CommandBar.tsx` — pole se zadáním, Enter odešle, Esc zavře, pod ním rozsah (vybrané uzly, jinak celé plátno).
- `components/DrawingBar.tsx` — lišta „Srdce čte skill… 12 s · krok 3 · obvykle ~60 s“ s Podrobnosti, Zrušit/Zavřít (jen schová lištu) a po skončení bez kreslení, chybě či zaseknutí „Otevřít Asistent“.
- `components/HeartWork.tsx` + `WorkSteps.tsx` — okno „Co srdce dělá“: průběh, živé kroky (`steps` ze stavu srdce, scroll dole), závěrečná odpověď nebo chyba, Zkusit znovu (vrátí text do pole), Otevřít Asistent. Samo se otevře při odpovědi bez kreslení a při chybě. Styl `styles/heart-work.css`, předpona `heart-work`.
- `logic/heart-work.ts` — které dávky jsou naše (zpráva s `context.flowId` od odeslání), fáze `queued` / `running` / `finishing` / `done-no-draw` / `error` / `stalled`, věta lišty a „co dělá“ z posledního kroku; test `heart-work.test.ts`, fixtury `heart-work.fixtures.ts`.
- `logic/command-bar.ts` — kdy se řádek otevře (`/`, Ctrl+K mimo pole), kontext zprávy a poznání, že srdce zapsalo draft; test `command-bar.test.ts`.
- `logic/use-command-bar.ts` — otevření, odeslání a čekání podle dávky srdce: každé ~2 s stav srdce (`/api/brain/heart/status`) a verze plátna; draft v plátně = hotovo, žádný pevný časový strop. Ukládá a načítá rodič (`LibraryCanvas`).
- `styles/command-bar.css`, předpony `command-bar` a `command-bar-status`.
- `components/EmptyPrompt.tsx` — výzva uprostřed prázdného plátna (bez uzlů, mimo přehrávání a kreslení): velké pole, Enter odešle, „Postavit“, tři příklady; chyba pod polem. Logika v `logic/empty-prompt.ts` (test `empty-prompt.test.ts`), styl `styles/empty-prompt.css`, předpona `empty-prompt`.
