# Hlášená chyba — uživatelovo minimalistické pravidlo

Tato reference se načítá jen pro **opravu kódu aplikace**, ne pro běžnou obsluhu.

1. Najdi přesné místo chyby ze současného zdroje a popisu uživatele.
2. Oprav minimálně. **Nepiš ani nespouštěj testy, nezakládej další review cyklus.**
   Neprováděj refaktor, redesign či nesouvisející opravy.
3. Zkontroluj aktuální Git větev a necommitnuté změny. Zachovej cizí práci.
   Commituj explicitně jen soubory této opravy.
4. Dostaň opravu do lokálního `main`. Neslučuj vedlejší rozpracované funkce.
   Není-li main stejná vývojová základna nebo by merge přibral jiné změny,
   přenes pouze konkrétní opravu; při nejasném konfliktu nepřepisuj cizí soubory.
5. Proveď pouze build potřebný k nasazení. Ověř skutečnou adresu localhostu,
   listener a servírovaný adresář. Nezaměň repozitářový dist za živý dist.
6. Aktualizuj vlastní náhled bez přepsání databáze; pokud jde jen o frontend,
   nevypínej backend. Před změnou uchovej původní statické soubory.
7. Zpětným HTTP čtením potvrď, že localhost servíruje nový build.
   Build ani HTTP kontrola nejsou důkaz, že uživatelův scénář funguje.
8. Zpráva: „Oprava je na lokálním main a URL. Obnov Ctrl+F5 a napiš výsledek.“
   Potom čekej na uživatelovo ověření, nepokračuj dalším testováním.

Lokální main není automaticky remote main: bez provedeného push neříkej,
že je změna na GitHubu. Při blokaci buildu či nasazení řekni přesný blocker.
Aplikace běží na 8740 (`opora.toml`), jiné servery mohou běžet na 8768/8780;
port ani proces nepřebírej bez aktuální identifikace. Žádné plošné kill/prune/reset.
