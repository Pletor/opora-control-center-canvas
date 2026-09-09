# Pracovní módy, kreslení a mapa
STATUS: READY — Astra, podle aktuálního zadání uživatele.

## Výsledek
Jeden projekt, tři módy: Struktura (dosavadní editor), Kreslení (Excalidraw 0.18.1, MIT, lazy-loaded), Mapa (projekce skutečných uzlů a vazeb). Levý přepínač a kontextové nástroje, horní Nastavení s mřížkou a přichytáváním. Ovládání vychází z dodaných obrázků, nekopíruje jejich obsah.

## Data
Kresba je oddělená od graphu. GET /api/drawing?project=&workspace=&layer= (prázdný layer = kořen); POST /api/drawing {project,workspace,layer,expected_revision,scene:{elements:[...]}}. Výsledek {scene,revision,readOnly,available,source,saved_at}. SQLite append-only revize/CAS. Main nemá import kresby z Gitu: read-only/unavailable. Ověřit scope/existenci vrstvy, archived project a pracovní prostor. GET nic nezapisuje.
Kreslení podporuje selection, freedraw, rectangle, diamond, ellipse, arrow, line, text a frame; bez image/embeddable/file importu v tomto řezu. Nejvýše 2000 elementů a 1.5MB JSON scény; ID unikátní str do120; konečná omezená geometrie, platný Unicode, žádné externí embeds. Neprovádět síťové importy. Ruční uložení, rozepsané scény zachovat při přepínání módu/vrstvy v otevřené aplikaci. Před úplným reloadem uložit. Konflikt nesmí přepsat cizí revizi.

## Mapa
Všechny uzly aktuálního projektu + skutečná struktura obsahuje a explicitní propojení. Obsahuje není totéž co explicitní vazba. Mapa neodvozuje moduly z názvů souborů a nepropojuje různé Git projekty. Klik výběr; otevření uzlu návrat do struktury. Umožnit explicitní propojení uzlů napříč vrstvami stejného projektu; původní graph formát zůstane kompatibilní, zruší se pouze omezení stejných rodičů. Struktura ukáže počet vazeb mimo svou vrstvu a odkaz do Mapy. Export typed JSON pro Archify; je to exportní integrace, ne vložený Archify renderer. Ověřit export příslušným schema/tool na fixture, netvrdit univerzální showcase kvalitu libovolného hustého grafu.

## UI a bezpečnost
Režim/vrstva v URL, preference mřížky lokálně v tomto prohlížeči. Kreslicí knihovna ani fonty nesmějí zpomalit boot struktury nebo vyžadovat CDN za běhu. Nastavení mění skutečné grid/snap chování, ne fiktivní přepínač. Žádné credentials ani LLM launch v nastavení. Smazání uzlu/projektu zahodí jen odpovídající klientské neuložené kresby; uložená historie zůstane. Při smazání nadřazeného uzlu z globální Mapy se navigace vrátí do existujícího kořene.

## Vlastnictví
Backend worker: backend/drawings.py, backend/app.py, backend/service.py, backend/graph.py, tests/test_drawings.py, tests/test_map_links.py a vlastní BACKEND-EVIDENCE.json. Parent: ostatní frontend, testy UI, export mapa helper, assets/build a integrace. Žádní dva writeři stejného souboru; parent vlastní git index/commity.

## Oracle
RED→GREEN API persistence/CAS/izolace, cross-layer edge; reálné kreslení tvarem/myší a save/reload v Playwright, přepínání módů/vrstev, main guard, grid/snap preferences, skutečné mapové vazby a export. Full regrese, audit závislostí a nezávislé review. Produkční obsah neměnit při testu ani nasazení.
