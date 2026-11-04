# ElevenLabs – hlas Pletora z placeného cloudu

Engine `elevenlabs` v `speech.py` (hlas `elevenlabs:voice`, v okně „ElevenLabs · Pletor_MH“ ve skupině
„cloud · ElevenLabs · text opouští počítač“ vedle Edge). **Text odpovědi odchází z počítače do ElevenLabs** a každý
znak se odečte z tarifu uživatele; posílá se jen text, který okno čte nahlas, nikdy podklady ani tajemství.

- `client.py` REST přes `urllib` (žádná nová závislost):
  - `settings()` nastavení z prostředí procesu, jinak z `.env` v kořeni repa (čte jen řádky `ELEVENLABS_*`);
  - `status()` dostupnost bez spotřeby znaků: `GET /v1/voices` (id hlasu podle jména, jednou, pak z paměti) a
    `GET /v1/user/subscription` → `quota {tier, character_count, character_limit}`; cache 60 s;
  - `stream(text)` `POST /v1/text-to-speech/{voice_id}/stream?output_format=mp3_44100_128`, MP3 po kouscích
    (stejný tvar jako Edge), timeout 20 s, text nejvýš 600 znaků (limit route);
  - chyby 401/402/403/429 → `EngineMissing` s českým důvodem („hlas Pletor_MH vyžaduje tarif Creator“, „klíč
    ElevenLabs nemá oprávnění…“, „vyčerpán limit znaků ElevenLabs“); route vrátí 503, `GET /voices` hlas ukáže
    jako nedostupný s důvodem (dalších 60 s), nikdy 500.
- `test_client.py` jen přes falešný transport: žádný skutečný požadavek, žádné znaky.

## Klíč a nastavení

Do `.env` v kořeni repa (je v `.gitignore`; aplikace jinak `.env` nenačítá) nebo do prostředí procesu:

```
ELEVENLABS_API_KEY=...            # tajné: nikdy do kódu, logu, odpovědi ani testu
ELEVENLABS_VOICE=Pletor_MH        # jméno hlasu na účtu (výchozí Pletor_MH)
ELEVENLABS_VOICE_ID=...           # volitelné, má přednost před jménem (není tajné)
ELEVENLABS_MODEL=eleven_flash_v2_5  # nebo eleven_multilingual_v2 (kvalitnější, pomalejší)
```

Klíč založ s omezenými oprávněními: **Text to Speech**, **Voices: Read**, **User: Read**. Ne „vše“: klíč
s plným přístupem umí mazat hlasy a měnit účet. Klíč jde jen v hlavičce `xi-api-key`, klientovi se nevrací.

## Cena a tarif

- Platí se znaky z tarifu uživatele (free 10 000 znaků/měsíc); zbytek ukazuje popisek hlasu v okně („zbývá
  8 400 znaků“, pod 10 % „pozor“), tooltip tarif a spotřebu.
- **Pletor_MH je profesionální klon (PVC)**: API ho pustí jen na tarifu **Creator a výš**. Na free/Starter vrací
  403 `subscription_required`; hlas je pak nedostupný s důvodem v tooltipu a nikdy není výchozí. Pro zkoušku na
  free tarifu stačí premade hlas (`ELEVENLABS_VOICE=Daniel`).
- Výchozí volba okna je nejlepší dostupný v pořadí XTTS → ElevenLabs → Edge → Piper → prohlížeč; „dostupný“ =
  ověřený kontrolou výše nebo posledním úspěšným čtením. Za zvoleným lokálním hlasem (XTTS, Piper) okno při výpadku
  nikdy nepadá do cloudu; za cloudovým může na další cloud a nakonec na lokální.
