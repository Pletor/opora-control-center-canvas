Platforma: git I/O (gitio), Windows job objekty pro ohraničené procesy (windows_job), identita buildu (build_identity), klient paměti OpenViking na loopbacku (openviking_client).

`openviking_client` posílá jen `X-API-Key`: server v režimu `api_key` odvozuje identitu z klíče a hlavičky `X-OpenViking-*` odmítá. `with_api_key` vyrobí klienta jedné role, `admin_*` metody rozdají rolím klíče. Hlavičky identity zapíná až `trusted_identity=True` pro nasazení `auth_mode: trusted`.

`git_read` čte historii gitu pro párování commitů se zadáním: revize, předky, seznam posledních commitů, trailery a změněné cesty, přejmenování souboru a SHA obsahu. Jen čtení, vše přes `gitio.git`.

`mirror_client` volá Zrcadlo (BioCortexAI, docs/zrcadlo.md) jen na `127.0.0.1`/`localhost`, bez proxy a přesměrování, s timeoutem 2 s; vypnuto, porucha nebo neplatná odpověď = `None`. Zapíná ho `[mirror]` v `opora.local.toml` přes `OPORA_MIRROR_URL` a `OPORA_MIRROR_PROJECTS`.
