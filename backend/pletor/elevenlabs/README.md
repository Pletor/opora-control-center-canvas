# ElevenLabs – hlasy Pletora z placeného cloudu

Engine `elevenlabs` v `speech.py` má víc hlasů ve skupině „cloud · ElevenLabs · text opouští počítač“ vedle Edge:

| id | v okně | hlas na účtu |
| --- | --- | --- |
| `elevenlabs:brian` | Brian · hluboký, konejšivý | premade „Brian - Deep, Resonant and Comforting“ |
| `elevenlabs:bill` | Bill · moudrý, vyrovnaný | premade „Bill - Wise, Mature, Balanced“ |
| `elevenlabs:custom` | jméno z `ELEVENLABS_VOICE` (Pletor_MH) | jen když je v `.env` `ELEVENLABS_VOICE` nebo `ELEVENLABS_VOICE_ID` |

Stará uložená volba `elevenlabs:voice` (jediný hlas do #334) znamená `custom`, a když není nastaven, `brian`.
Neznámý klíč (`elevenlabs:rachel`) je `VoiceMissing` → route 404.

**Text odpovědi odchází z počítače do ElevenLabs** a každý znak se odečte z tarifu uživatele; posílá se jen text,
který okno čte nahlas, nikdy podklady ani tajemství.

- `client.py` REST přes `urllib` (žádná nová závislost):
  - `settings()` nastavení z prostředí procesu, jinak z `.env` v kořeni repa (čte jen řádky `ELEVENLABS_*`);
  - `voices()` klíče hlasů a štítky, `key(id)` id → klíč (stará volba, neznámý hlas);
  - `status(klíč)` dostupnost bez spotřeby znaků: účet jednou (`GET /v1/user/subscription` → `quota {tier,
    character_count, character_limit}`, klíč, síť) a každý hlas zvlášť (`GET /v1/voices`, id podle jména nebo části
    před „ - “, jednou, pak z paměti); cache 60 s;
  - `stream(text, id)` `POST /v1/text-to-speech/{voice_id}/stream?output_format=mp3_44100_128`, MP3 po kouscích
    (stejný tvar jako Edge), timeout 20 s, text nejvýš 600 znaků (limit route);
  - chyby 401/402/403/429 → `EngineMissing` s českým důvodem („hlas Pletor_MH vyžaduje tarif Creator“, „klíč
    ElevenLabs nemá oprávnění…“, „vyčerpán limit znaků ElevenLabs“); route vrátí 503, `GET /voices` **jen ten hlas**
    ukáže jako nedostupný s důvodem (dalších 60 s), ostatní hrají dál; nikdy 500.
- `test_client.py` jen přes falešný transport: žádný skutečný požadavek, žádné znaky.

## Klíč a nastavení

Do `.env` v kořeni repa (je v `.gitignore`; aplikace jinak `.env` nenačítá) nebo do prostředí procesu:

```
ELEVENLABS_API_KEY=...            # tajné: nikdy do kódu, logu, odpovědi ani testu
ELEVENLABS_VOICE=Pletor_MH        # volitelné: vlastní hlas `custom` podle jména na účtu
ELEVENLABS_VOICE_ID=...           # volitelné, má přednost před jménem (není tajné)
ELEVENLABS_MODEL=eleven_multilingual_v2  # výchozí; eleven_flash_v2_5 = rychlejší, o něco horší čeština
```

Klíč založ s omezenými oprávněními: **Text to Speech**, **Voices: Read**, **User: Read**. Ne „vše“: klíč
s plným přístupem umí mazat hlasy a měnit účet. Klíč jde jen v hlavičce `xi-api-key`, klientovi se nevrací.

## Model

| model | první zvuk | čeština | cena na free tarifu |
| --- | --- | --- | --- |
| `eleven_multilingual_v2` (výchozí) | ~0,5–0,7 s | nejlepší | 1 kredit za znak |
| `eleven_flash_v2_5` | ~0,2 s | o něco horší | 1 kredit za znak |

Model platí pro všechny hlasy; `ELEVENLABS_MODEL` ho přepíše.

## Cena a tarif

- Platí se znaky z tarifu uživatele (free 10 000 znaků/měsíc), jeden účet pro všechny hlasy; zbytek ukazuje popisek
  skupiny ElevenLabs v okně („zbývá 8 400 znaků“, pod 10 % „pozor“), tooltip hlasu tarif a spotřebu.
- Brian a Bill jsou premade hlasy: přes API jdou i na tarifu free.
- **Pletor_MH je profesionální klon (PVC)**: API ho pustí jen na tarifu **Creator a výš**. Na free/Starter vrací
  403 `subscription_required`; `custom` je pak nedostupný s důvodem v tooltipu a nikdy není výchozí, Brian a Bill ne.
- Výchozí volba okna je nejlepší dostupný v pořadí XTTS → ElevenLabs (první dostupný z Brian, Bill, custom) → Edge
  → Piper → prohlížeč; „dostupný“ = ověřený kontrolou výše nebo posledním úspěšným čtením. Za zvoleným lokálním
  hlasem (XTTS, Piper) okno při výpadku nikdy nepadá do cloudu; za cloudovým může na další cloud a nakonec na lokální.
