# Pravidla GitHub review a kontrol

OporaHub vyhodnocuje načtené důkazy podle pravidel konkrétního projektu a prostoru.
Výsledek vždy patří jedné revizi pravidel, přijaté revizi plánu a SHA pull requestu.
Jde o místní podmínky pro kontrolu práce; jejich splnění samo nepřijímá plán,
neuzavírá kartu, nemerguje kód a nenasazuje aplikaci.

## Nastavení

Nejprve načtěte [GitHub důkazy](oporahub-github.md) příslušného PR. Člověk pak
nastaví povinné kontroly, povolené účty reviewerů, požadovaný počet schválení kódu
a plánu a maximální stáří pozorování. Před aktivací prohlédne přesný souhrn.
Repozitář a cílová větev pocházejí ze serverové konfigurace a uloženého pozorování.
Číselná identita repozitáře chrání před záměnou novým repozitářem stejného jména.

Kontrola je určena dvojicí **ID aplikace a přesný název kontroly**. Pouhá shoda
názvu nestačí. Jméno účtu reviewera slouží pro orientaci; rozhoduje číselné ID.
Reviewer musí mít při načtení serverově doložené oprávnění k zápisu a nesmí být
bot ani autor PR. Různé účty neprokazují různé fyzické osoby. Lokální autor plánu
zatím není propojený s ověřeným GitHub účtem.

Každá změna pravidel vytváří neměnnou revizi. Souběžná změna jiným operátorem
vyvolá konflikt a vyžaduje novou kontrolu. Vypnutí také vytvoří revizi; historii
nesmaže. Agent smí načítat důkazy, pravidla však mění člověk.

Po aktivaci nebo změně pravidel načtěte nové pozorování. Dřívější důkazy zůstávají
v historii, ale nemohou samy splnit novou revizi pravidel. Bez pravidel jsou
kontroly pouze pozorované; vypnutá pravidla nikdy neznamenají automatické splnění.

## Jak se rozhoduje

Povinná kontrola musí pro přesné SHA skončit stavem completed/success.
Novější běh téže kontroly, který ještě čeká, nahrazuje starý úspěch. Chybějící,
přeskočené, neutral, neúplné nebo rozporné údaje nesplní podmínku. Commit statuses
jsou nadále informativní, protože v této integraci nemají identitu poskytovatele
potřebnou pro tato pravidla. ID aplikace GitHub Actions a název kontroly nejsou
zárukou konkrétního workflow; pravidla nepřebírají branch protection GitHubu.

Review kódu vyžaduje stanovený počet různých povolených účtů schvalujících přesné
SHA. Review plánu navíc vyžaduje samostatný přesný řádek:

```text
Opora-Plan: <project>/<workspace>@<acceptedRevision>
```

Stejné review může splnit obě kategorie, pokud obsahuje tento řádek. Komentář
nepřepisuje dřívější rozhodnutí; novější rozhodnutí či dismissal ano. Platný
požadavek na změny oprávněného reviewera blokuje splnění i mimo seznam účtů,
jejichž schválení se započítávají. Neznámá oprávnění nemohou potajmu odstranit
blokující rozhodnutí. Zavřený nebo draft PR pravidla nesplní.

## Stáří a souběžné načítání

Každý pokus o načtení má serverové pořadové číslo. Zahájení novějšího pokusu
zneplatní aktuální použitelnost starého úspěchu. Chyba sítě nebo přerušený pokus
zanechá stav neznámý; staré zelené hodnocení se neobnoví jako náhrada. Pozdní
odpověď staršího pokusu nepřekoná novější pokus.

Maximální stáří se počítá od začátku načítání, nikoli jeho konce. Panel ukazuje
interval pozorování a konec jeho platnosti. Změna plánu, pravidel, konfigurace,
identity repozitáře nebo SHA vyžaduje odpovídající nové důkazy. Načítání více
GitHub API není atomický snímek; platné místní hodnocení nepotvrzuje nepřetržitě
aktuální stav vzdáleného GitHubu.

Historický detail stále obsahuje původní důkazy. Starší snímky bez pořadí pokusu
a intervalu se nepřepisují ani zpětně nedoplňují domnělými časy. Pro současné
splnění pravidel je potřeba nové načtení.

## Uložení a API

Nové tabulky uchovávají neměnné revize pravidel, aktuální odkaz a pořadí pokusů.
Aktivace pravidel používá transakci a očekávanou aktuální revizi. Síťové čtení
probíhá mimo projektové zámky; před uložením výsledku se kontext znovu kontroluje.
Obnova staré migrační zálohy nesmí tuto historii zahodit.

Rozhraní `/api/oporahub/review-policy` poskytuje kontext a aktivaci;
`/history` historii, `/disable` výslovné vypnutí a `/status` aktuální hodnocení
vybraného PR. Dosavadní GitHub důkazy dostávají samostatné `policyEvaluation`;
původní hodnocení pozorovaných kontrol zůstává oddělené. Přesné datové typy,
limity a ověřovací podmínky jsou v [implementačním kontraktu](oporahub-review-policy-contract.md).