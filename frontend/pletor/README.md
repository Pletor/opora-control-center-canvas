Okno Pletor: jeden chat s Pletorem (Jarvis nad srdcem a Brainem), kontrakt `docs/navrhy/2026-11-04-pletor-jarvis.md`, milník P1.
Pletor nezapisuje na plátno; záměr předá srdci a rozhodnutí zapíše do Schránky. Okno to ukazuje chipy provedených akcí.

Režimy (`PletorMode`, drží `App.tsx`): `hud` (kokpit přes celou obrazovku, nejvyšší vrstva), `window` (plovoucí okno s koulí), `closed`. Každý start OPORY začíná v `hud`; režim se neukládá a je jeden pro všechny projekty. „Vstoupit do OPORY“ nebo Esc (mimo rozepsané pole) → `window`; tlačítko Pletor v liště: zavřený → okno, okno → HUD, Shift+klik → HUD; ⛶ v okně → HUD; `closed` jen křížkem v okně. Projekt a prostor jsou jen kontext.

Dílky (`components/`):

- `PletorButton`: tlačítko v horní liště vedle Asistenta, hlásí klik (a Shift); režim mění App.
- `PletorWindow`: rodič. Drží stav konverzace a odesílá (`usePletor`); podle režimu skládá okno nebo `PletorHud`.
- `PletorHud`: rodič kokpitu (zelený Jarvis HUD): lišta, plátno s rohy, konzole s protokolem a příkazový řádek; Esc → okno.
- `PletorHudBar`: horní lišta (PLETOR, čas, uptime od startu aplikace, stav srdce, „Vstoupit do OPORY“).
- `PletorHudCanvas`: plátno s rAF smyčkou (DPR max 2, ResizeObserver, stojí ve skryté záložce, téměř statické při reduced motion).
- `PletorHudCorners`: rohové readouty (projekt, mozek `claude` nebo `ollama · <model>` z `brainText`, FPS, stav, eskalace) a štítek stavu. Mozek se přepíná větou v chatu, ne tlačítkem.
- `PletorHeartLine`: jeden řádek se stavem srdce a počtem čekajících eskalací.
- `PletorOrb`: svítící jádro nad rozhovorem (dýchá / přemýšlí / záblesk odpovědi / chyba); stav mu dává rodič.
- `PletorMessages`: zprávy, člověk vpravo, Pletor vlevo.
- `PletorActions`: po odpovědi chipy akcí (Poslal jsem srdci / Zapsal do Schránky / Selhalo).
- `PletorComposer`: pole a tlačítko Odeslat, Enter odešle; při poslechu ukazuje průběžný přepis. Mezi pole a Odeslat dá rodič ovladače hlasu.
- `PletorMicButton` (P3): mikrofon; klik = poslouchej, klik/Esc = stop, při čtení odpovědi ji klik utne. Bez rozpoznávání řeči (Firefox) jen značka „bez hlasu“, nepovolený mikrofon tlačítko vypne.
- `PletorVoiceToggles` (P3): přepínače Konverzace (po domluvení znovu poslouchá; jinak jedna věta a konec) a Hlas (odpovědi nahlas i na psané zprávy).

Hlas (P3) jde přes prohlížeč: `SpeechRecognition` (cs-CZ) a `speechSynthesis`, zdarma a bez klíčů. Rozpoznaná věta se odešle sama (stejně jako Enter, s `voice: true`), odpověď se přečte nahlas, když zpráva vznikla hlasem nebo je zapnutý Hlas. Esc, mikrofon nebo začátek řeči čtení utne. HUD má stavy `listening` a `speaking`; jádro sleduje hlasitost mikrofonu (`AnalyserNode`, jinak syntetická vlna) a hranice slov při čtení.

Logika (`logic/`):

- `pletor-client.ts` (test vedle): `POST /api/pletor/messages`, `GET /api/pletor/state`, mapování odpovědi na texty okna, typ režimu.
- `hud-palette.ts` (test vedle): zelená paleta kokpitu (chyba tlumeně červená), stav jádra z `orbMode`, rychlost a amplituda.
- `hud-draw.ts` (test vedle): `drawHud(ctx, frame, palette, state)` kreslí prstence a jádro, `stepHud` posouvá natočení a amplitudu.
- `pletor-orb-mode.ts` (test vedle): stav jádra z odesílání, chyby a času poslední odpovědi.
- `voice-input.ts` (test vedle): rozhraní `VoiceInput` nad `SpeechRecognition`, české hlášky chyb (`voiceError`), volitelná hlasitost mikrofonu (`openMicLevel`). V P3b se vymění za lokální Whisper.
- `voice-output.ts` (test vedle): rozhraní `VoiceOutput` nad `speechSynthesis`: dělení na věty, výběr českého hlasu, `stop` = barge-in. V P3b se vymění za lokální TTS.
- `voice-prefs.ts` (test v `voice-output.test.ts`): Konverzace a Hlas v `localStorage`, jeden klíč pro aplikaci.
- `use-pletor-voice.ts`: hook hlasu (poslech → auto-odeslání → čtení → v Konverzaci znovu poslech, Esc, úklid mikrofonu).
- `pletor-poll.ts`: polling stavu každé 4 s, jen když je okno otevřené (sdílený `usePolling`), a odeslání zprávy.

Styl: `styles/pletor.css` (sdílené zelené proměnné `--pletor-*`, blok `pletor`, tlačítko `pletor__toggle`, jádro `pletor-orb`) a `styles/pletor-hud.css` (blok `pletor-hud`).
