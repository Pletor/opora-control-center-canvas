# Změny a odstranění přijatého grafu

Návrhy změn grafu navazují na [první přijetí grafu](oporahub-graph-proposals.md).
Umožňují upravit existující prvky a vazby nebo je výslovně odstranit. Návrh
Canvas nemění; změny provede až člověkem přijatá revize. Historie návrhů,
přijatých zadání a grafových manifestů zůstává společná.

U staršího neprázdného plátna bez přijatého manifestu nejprve použijte
**Převzít stávající graf**. Tento návrh nic nepřidává; ukáže existující graf
a přebíraná zadání k výslovnému prvnímu přijetí. Není třeba vytvářet pomocnou
kartu. Po přijetí lze navrhovat úpravy jeho prvků.

## Co člověk přijímá

Kontrola rozlišuje tři hodnoty: přijatou, aktuálně pracovní a navrženou.
Návrh mění pouze vybraná pole. Přejmenování karty například nesmí současně
přijmout její rozpracovanou změnu rodiče nebo účelu. Přijatý a pracovní graf
se upravují odděleně; nedotčené pracovní změny zůstávají nepřijaté.

Takto lze výslovně přijmout i změnu, která již byla provedena na plátně.
Chybějící pracovní uzel lze výslovně odstranit také z přijatého plánu.
Pouhá úprava jeho pole jej ale potají neobnoví: pro obnovu pracovního stavu
použijte historii plátna a potom nový návrh.

Před přijetím je potřeba potvrdit kontrolu konkrétního neměnného návrhu.
Potvrzení se ruší při obnovení kontextu, přepnutí prostoru či návrhu a při
převodu na nového rodiče. Přijetí plánu není potvrzení správnosti kódu.

## Odstranění a důkazy

Odstranění uvádí přesná ID uzlů a vazeb. Závislé potomky a incidentní vazby
je nutné výslovně zahrnout, případně v témže návrhu změnit jejich vazbu na
odstraňovaný prvek. Systém sám seznam odstraňovaných prvků nerozšiřuje.
Oblast není strom vlastnictví: její odstranění nesmaže geometricky obsažené
karty. Změna jejich příslušnosti k oblasti musí být viditelná při kontrole.

Zůstávající odkazy bran a větví bloků je nejprve nutné vyřešit; nemění se
potají na jiný cíl. Ochrany uzavřených karet zůstávají účinné. Změna významu
nebo odstranění takové karty vyžaduje její předchozí otevření člověkem.

Historie specifikací, textů, kreseb, prostorů agentů, běhů, epoch a výsledků
se nemaže. Nová přijatá revize už neobsahuje dokumenty odstraněných uzlů;
starší revize je nadále obsahují. Úklid aktuálního pracovního stavu má v návrhu
zachycenou původní i výslednou podobu. Tickety se neztrácejí spolu s kartou.
V panelu běhů lze zobrazit všechny karty včetně odstraněných a otevřít jejich
původní výsledky i tehdy, když na plátně nezůstala žádná karta.

Změna koncových uzlů vazby nesmí převzít aktuální hlášení původní vazby jako
důkaz pro nové spojení. Jeho vyřazení z aktuálního stavu je součástí kontroly;
původní obsah zůstává v neměnném záznamu.

## Konflikty a souběžná práce

Změní-li se sdílená architektura projektu ve vlastním workflow, přijatý plán
stále odkazuje na její předchozí kontext. Volba **Převzít aktuální kontext
architektury** vytvoří návrh s viditelným původním a současným kontextem.
Jeho přijetí aktualizuje závislost plánu; sdílenou architekturu samo nepřepisuje.
Pokud nové uspořádání vyžaduje změnu rodičů karet, musí být součástí výslovného
návrhu. Bez této volby se cizí změna architektury automaticky nepřebírá.
Kontrola zahrnuje také aktuální zadání prvků architektury a jejich revize.
Změna těchto zadání po vytvoření návrhu přijetí zablokuje. Nová přijatá revize
zachytí aktuální závislosti; historická zadání odstraněných prvků zůstávají
ve starších revizích. Sdílená zadání se při této operaci nepřepisují.

Přijetí ověřuje přijatou hlavu, pracovní graf a zachycený stav. Cizí změna
od vytvoření návrhu znamená konflikt. Výslovný `rebase` vytváří nový návrh;
nezmění původní historii ani sám nic nepřijme. Nezávislé změny lze přenést,
pokud se nezměnily dotčené původní hodnoty a význam odkazovaných prvků.
Konflikt stejného pole vyžaduje nový vědomý návrh.

Posun přijaté revize zneplatní dosavadní oprávnění vykonávání podle stávajícího
protokolu. Starý běh nemůže odevzdat nový výsledek; přesné opakování již
uloženého výsledku nadále vrátí jeho původní potvrzení. Rezervace se nemění
na nový běh a epocha se nevrací zpět. Neaktuální rezervaci může být nutné
uvolnit nebo počkat na její expiraci.

## API a uložení

Používá se stejný prefix `/api/oporahub/graph-proposals`. Starší neměnné
záznamy `graph-additions` zůstávají čitelné i přijímatelné. Nová verze návrhu
má `schemaVersion: 2` a `kind: "graph-changes"` a vyžaduje přijatý manifest.

`plan` může vedle přírůstků obsahovat:

- `updateNodes: [{id, fields}]` s výslovně vybranými poli;
- `removeNodes: [id]`;
- `updateEdges: [{id, source, target, port}]`;
- `removeEdges: [id]`.

Volitelné `adoptArchitectureContext: true` znamená výslovné převzetí aktuálního
kontextu sdílené architektury, nikoli oprávnění ji měnit. Samostatný návrh tohoto
převzetí je možný jen tehdy, když se kontext skutečně liší.

Výchozí hodnoty a výsledné grafy vytváří server. Klient je nesmí podvrhnout.
Přijetí této verze přidává k dosavadním očekáváním `reviewedChangesId`, které
musí odpovídat přesně prohlédnutému návrhu; `adoptBaseGraphDigest` je `null`.
První převzetí grafu zůstává samostatným postupem staršího typu návrhu.

Pracovní graf, změněný aktuální stav, manifest, přijatá revize a její hlava
se zapisují v jediné SQLite transakci. Chyba kteréhokoli zápisu nesmí ponechat
část změny přijatou. Opakované přijetí vrací původní výsledek a nevrací hlavu
zpět. Platí stejná pravidla databázové autority, záloh a jednoho serverového
procesu jako u návrhů nových karet.

Tento protokol nemění sdílenou architekturu, druh existujícího uzlu, kód,
texty a kresby ani konfiguraci bran a kontrol. Zadání se dále mění vlastním
typem verzovaného návrhu. Přijetí grafu samo nepovoluje merge nebo nasazení.
