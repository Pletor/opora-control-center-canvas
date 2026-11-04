# Pletor – plynulá hlasová konverzace

Cíl: odezva a chování jako u ChatGPT hlasu, bez dalšího účtu. Předplatné ChatGPT hlas pro cizí aplikace nedává (Advanced Voice nemá API, Realtime API se účtuje zvlášť), proto zůstává řetěz poslech → Claude → TTS a zrychluje se jeho skládání.

Měření (2026-11-04, `claude -p`, persona, bez podkladů): první slovo ~1,4 s, celá odpověď ~3 s; Haiku rychlejší není (první slovo ~2,0 s). Model se proto nemění; vyhrává se tím, že se nečeká na celou odpověď.

## Prvky

1. **Streamování po větách (S1).** Backend posílá odpověď průběžně, okno čte první větu, zatímco model píše další.
2. **Přerušení hlasem (S2).** Když člověk během čtení začne mluvit, Pletor hned ztichne a poslouchá.
3. **Dřívější konec věty (S3).** Ustálený průběžný přepis se po krátké pauze (~700 ms) bere za hotovou větu, místo čekání na finální výsledek prohlížeče.
4. **Krátké odpovědi.** Beze změny: režim HLAS už chce nejvýš dvě věty.

## Rozhraní S1

`POST /api/pletor/messages/stream` s tělem jako `POST /api/pletor/messages` vrací `application/x-ndjson`, jeden objekt JSON na řádek:

- `{"type": "delta", "text": "<další kus pole reply>"}` – nula a více; kousky dají po složení přesně `reply`.
- `{"type": "done", "reply": "...", "actions": [{type, text, ok, detail?}]}` – vždy poslední, stejný tvar jako `PletorReplyOut`. Chyba modelu je `done` s textem chyby a bez akcí. Přepínací věta mozku je jen `done`.

Zprávy se ukládají stejně jako dnes (člověk hned, Pletor na konci). `POST /messages` zůstává beze změny.
Claude: `--include-partial-messages`, z `stream_event` `text_delta` se skládá text modelu a z něj se průběžně vytahuje řetězec pole `"reply"` (bez uvozovek a escape). Ollama zatím neprobíhá po proudu: jeden `delta` s celou odpovědí a `done`.

## Okno

`sendPletorMessageStream` čte proud; kousky textu jdou do `createServerOutput` přes `begin(events)` → `{ push(text), end() }`, které věty dělí `splitSentences` a každou dokončenou hned objedná u TTS (stejná fronta, stejný řetěz záloh). Zápis do rozhovoru a akce se chovají jako dosud po `done`.
