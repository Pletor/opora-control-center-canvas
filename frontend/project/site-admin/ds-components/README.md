# Components design systému

Sekce Components Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §3): `design.components[{name, group, summary, readme, preview, height}]` po skupinách, každá s živým náhledem a README.

- `components/ComponentsSection.tsx`: přepínač tématu náhledů, „+ Komponenta“, skupiny a karty (náhled, jméno, souhrn, README). Komponenta `Button` nese štítek „z Tlačítek webu“ a místo editoru vede do Tlačítek webu: skládá ji server (`backend/project/site_admin/button_component.py`) a poslaná by se zahodila.
- `components/ComponentPreview.tsx`: iframe `sandbox=""` (bez `allow-scripts`) se `srcdoc` z `previewDocument`.
- `components/ComponentEditor.tsx`: jméno, skupina, výška (40–4000), souhrn, HTML náhledu a README s náhledem markdownu (`ds-overview/MarkdownPreview`).
- `logic/components.ts` (+ test): skupiny, jméno podle gramatiky tokenů, stejný filtr náhledu jako server (`<script`, `on…=`, `javascript:`, `&#`, iframe/embed/object), meze výšky a dokument náhledu: CSP `default-src 'none'` se styly a obrázky/fonty jen z OPORY, `tokens.css` a `components.css` uložené revize (fonty a `assets/…` přepsané na API projektu) a `data-theme` na `<html>`.

Dílek nic neukládá: celý nový seznam hlásí `onChange` rodiči (`SitePanel` → `use-site-admin`). Náhledy stojí na CSS uložené revize, rozepsané tokeny se ukážou až po Uložit.
