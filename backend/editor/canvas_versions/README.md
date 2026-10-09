# Verze pracovního prostoru

Kontrakt: `docs/verze-platna.md`. Router: `backend/api/editor/canvas_version_routes.py`.

`canvas_versions.py` vlastní seznam, uložení, neměnné čtení a obnovu existující tabulky `canvas_versions`. Nové snapshoty zahrnují graf, Desktop, specifikace, texty, deníky, kresby, editovatelný prostor agenta, dokumentaci a dostupné místní přílohy. Staré řádky bez snapshotu zůstávají explicitně částečné.

`version_content.py` popisuje revizní úložiště, sémantický digest a token aktuálního obsahu. `version_assets.py` zachycuje místní soubory a zajišťuje návrat souborových zápisů při výjimce. `version_restore.py` validuje obnovu před zápisem a obnovuje obsah v nových, monotónních revizích.

Obnova vyžaduje token aktuálního pracovního prostoru, používá společnou databázovou transakci a při výjimce vrací souborové změny. Uchová záchrannou verzi odlišného současného obsahu. Neobnovuje společný cíl/nastavení projektu, zdrojový kód, Git historii, externí reference ani neměnné důkazy agentů. Kontext cíle zůstává ve snapshotu pro orientaci a kontrolu souběhu.