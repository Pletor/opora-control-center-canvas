# Technologické podklady V1 a V3

Načteno 8. 11. 2026. Tyto podklady dokládají technologické chování, nikoliv nasazení nebo konfiguraci AmpleLab. Použitou verzi PostgreSQL a rozšíření je nutné doložit zvlášť z projektu nebo běžící databáze; bez ní zůstává kompatibilita otevřená.

## Supabase RLS

[Primární dokumentace](https://supabase.com/docs/guides/database/postgres/row-level-security): RLS může používat serverem spravovaná `app_metadata`; uživatelsky měnitelná `user_metadata` nejsou vhodným základem autorizace. Obsah JWT může být do obnovení tokenu zastaralý. Role `service_role` obchází RLS, takže samotná existence politik neprokazuje izolaci backendových dotazů. Obalení funkcí `auth.uid()` nebo `auth.jwt()` skalárním `select` umožňuje vyhodnocení přes initPlan na příkaz místo pro každý řádek. Použitelnost musí být ověřena konkrétním dotazem a plánem vykonání.

## Vlastní claims

[Primární dokumentace RBAC](https://supabase.com/docs/guides/api/custom-claims-and-role-based-access-control-rbac), stránka uvádí aktualizaci 23. 10. 2026: Custom Access Token Auth Hook může doplnit claims před vystavením tokenu. Dokumentace ukazuje role a oprávnění použité v RLS. Nepotvrzuje, že je tento hook nebo Supabase Auth zapojen v AmpleLab; to musí ukázat kód a konfigurace aplikace.

## pgvector

[Primární README](https://github.com/pgvector/pgvector), aktuální instalační příklad odkazuje na `v0.8.7`: HNSW podporuje indexování `vector` do 2 000 dimenzí a `halfvec` do 4 000. Nejde o tvrzení, že jsou oba typy numericky totožné. U přibližného indexu filtr po průchodu kandidátů může snížit počet výsledků. Iterative scans jsou dostupné od `0.8.0`, lze nastavit striktní nebo uvolněné pořadí a limit dalšího hledání. Sdílený přibližný index mezi tenanty může ovlivňovat recall a rychlost. Dostatečnost konkrétního filtru projektu, počtu výsledků a nastavení indexu musí prokázat test aplikace. Samotné `vector(1024)` nepředepisuje přechod na `halfvec`, ani neřeší verzi embeddingového modelu či přepnutí aktivní sady.
