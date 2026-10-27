# Studio · přepínač vrstev

Přepínač **Skutečnost | MODEL** v liště Studia (`docs/studio.md` §1). Volba je v adrese (`studioLayer=model`), MODEL je
k dispozici v doméně a pod ní a ukazuje model té domény; na úrovni projektu se ukáže Skutečnost a parametr zmizí.

- `components/StudioLayerSwitch.tsx` – dvoudílný spínač, volbu hlásí rodiči.
- `logic/studio-layer.ts` – adresa, doména modelu (`modelDomainOf`), platná vrstva a karty OPORY domény, na které se
  smí technická karta vázat (`bindingCards`, se skutečným stavem); `logic/use-studio-layer.ts` – hook nad adresou.
- `styles/studio-layer.css`, blok `studio-layer`.
