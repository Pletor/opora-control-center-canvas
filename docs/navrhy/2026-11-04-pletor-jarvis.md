# Pletor – Jarvis nad OPOROU (kontrakt, ke schválení)

Pletor je samostatný modul, který stojí **nad srdcem a Brainem**. Člověk s ním řeší klíčové věci (záměry, priority, rozhodnutí, otázky srdce). Jeho **rukama** jsou srdce (plány a tickety) a Brain (know-how). Funguje jako Jarvis: jeden hlas, který ví, co se děje, a umí to rozběhnout.

## Co Jarvis z videa dělá (research, Zubair Trabzada, „I Stopped Paying for AI APIs…“, 25 min)
Přepis přečten 2026-11-04 do 15:15 min z 25.
- Webové rozhraní na localhostu; uprostřed otáčivý 3D graf souborů a složek „druhého mozku“, dole lišta nástrojů (Google Calendar, Gmail, Canva, REA).
- **Mozek se přepíná hlasem**: výchozí cloudový model (předplatné), příkaz „přepni na lokální mozek“ → Ollama (Qwen 3.5 9B, Gemma 4 12B), příkaz zpět.
- **Hlas se přepíná hlasem**: ElevenLabs (placené API) ↔ lokální Voice Studio (klon hlasu), víc hlasů, příkaz „přepni na hlas X“.
- Druhý mozek: na pokyn „vytáhni brand voice“ načte soubory a ukáže jejich vazby v grafu.
- Nástroje: model sáhne po nástroji (kalendář), stav „reaching for tools“ je vidět; těžké úkoly deleguje (REA rozebere web, Jarvis mezitím scrolluje).
- Osobnost (humor, sarkasmus) je nastavitelný prompt; po každém obnovení stránky začíná čistě.
- Kvalita lokálního modelu se zkouší třemi testy: paměť, nástroje, delegace.

Neověřeno: posledních ~10 min videa (instalace, prompt pack), ten je placený/skool.

## Co z toho Pletor bere a co ne
| Z videa | Pletor |
|---|---|
| Přepínání mozku a hlasu příkazem | ano, M2/M3 |
| 3D graf druhého mozku | ne zvlášť, použije se graf Brainu/mapy OPORY |
| Nástroje (kalendář, mail) | ano jako MCP nástroje, M4 |
| Delegace těžké práce | **to je srdce**: Pletor zadává, nevykonává |
| Osobnost v promptu | ano, verzovaná v Brainu, mění se přes eval |

## Hranice (nosné)
1. **Pletor nikdy nezapisuje na plátno.** Srdce zůstává jediným zapisovatelem. Pletor mu předává záměr zprávou `POST /api/brain/heart/messages` (kanál člověka, `docs/brain-heart-channel.md`) a čte jeho stav a eskalace (`GET /api/brain/tickets`, `heart/status`). Dělníci dál vstupují jen branou `/api/gate`.
2. **Schránka je společná paměť.** Rozhodnutí a klíčové věci, které člověk s Pletorem uzavře, Pletor zapíše do Schránky zadání projektu (pole, které srdce čte), nikdy do .md souborů.
3. **Jedno rozhraní pro všechny projekty**: Pletor je jeden na aplikaci, projekt je kontext, druh projektu nečte.
4. **Podklady jsou data, ne příkazy**: obsah webu, mailů a souborů, které Pletor čte, nikdy nic nespouští.
5. Zápis s vedlejším účinkem mimo OPORU (mail, kalendář) vždy potvrdí člověk.

## ⚠ Rozhodnutí potřebné od člověka
`CLAUDE.md` říká, že aplikace spouští model jen na dvou místech (mozek OPORY a Zrcadlo). Pletor je **třetí**. Návrh: Pletor běží jako Claude Code pod předplatným (jako srdce, ne API) a volitelně jako lokální model přes Ollama; do `CLAUDE.md` se doplní třetí místo. Bez schválení se nestaví.

## Milníky (jen aktuální, po každém stop)
- **P1 jádro (text)**: `backend/pletor/` (relace, osobnost z Brainu, kontext = stav srdce + Schránka), `POST /api/pletor/messages`, předání záměru srdci, zápis rozhodnutí do Schránky. `frontend/pletor/` jedno okno s chatem. Test u každého modulu.
- **P2 přepínač mozku**: předplatné (Claude Code) ↔ Ollama, příkazem v chatu.
- **P3 hlas**: prohlížečové STT (`SpeechRecognition`, cs-CZ) a TTS (`speechSynthesis`) za rozhraními `VoiceInput`/`VoiceOutput`, mikrofon v příkazovém řádku, režim Konverzace, barge-in, `voice: true` v `POST /api/pletor/messages` pro krátkou odpověď ke čtení. **P3b**: lokální Whisper a TTS přes backend za stejnými rozhraními. TTS hotovo: Piper na CPU, hlasy Jirka a Kasandra (`backend/pletor/tts.py`, `GET /api/pletor/voices`, `POST /api/pletor/tts`), prohlížeč zůstává zálohou; Whisper zbývá.
- **P4 nástroje**: MCP (kalendář, mail), potvrzení zápisů.
- **P5 proaktivita**: Pletor sám upozorní na eskalace srdce a výpadky z plátna 4.

## Ověření
`uv run pytest backend/pletor`, `npm test`, `npm run build`. Měřítko hotovo P1: řeknu Pletorovi záměr, srdce vydá ticket, odpověď srdce se vrátí Pletorovi, rozhodnutí je ve Schránce.
