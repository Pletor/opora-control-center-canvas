# Sekce stránky

Sdílený dílek, ve kterém člověk skládá sekce stránky (`site.sections`, `docs/architektura-pro-agenty.md` §3.1). Používá ho formulář stránky ve Struktuře plátna 2 (`domain-site/components/PageIntentFields.tsx`) i záložka **Stránka** v Detailu prvku (`element-detail/components/PageTab.tsx`): jedno rozhraní, dvě místa.

- `components/PageSectionsEditor.tsx`: blok na sekci – role, název (povinný, do 60 znaků), záměr (do 200), ↑ ↓, Odebrat a pod tím **Čím posouvá** (`moves`, do 120 znaků: čím sekce posouvá zákazníka v kroku cesty) – a pod seznamem **+ Přidat sekci** (nejvýš 20). Dostane celý `site` a každou změnu vrací jako celý `site`; nic neukládá, ukládá rodič.
- Logika bez Reactu (`addSection`, `updateSection`, `moveSection`, `removeSection`, `pageSiteForSave`, limity) je v `domain-site/logic/page-site.ts` s testem vedle; prázdné `moves` se při uložení vynechá.
- `styles/page-sections.css` (předpona `page-sections__`): zalamuje se podle vlastní šířky (container query), takže v úzkém Detailu prvku jde záměr a tlačítka na další řádek.
