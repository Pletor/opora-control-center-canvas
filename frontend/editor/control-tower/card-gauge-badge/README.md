# card-gauge-badge (odznak měřáku karty ve Velínu)

Malý dílek na pilulce karty ve Velínu (`docs/navrhy/2026-10-30-metriky-a-spoustece.md` §7, řez 4). Z `gauge`
agent-state (`GET /api/oporahub/agent-state`, `cards[].gauge`) ukáže:

- štítek složitosti `run.label` (XS–XL, nebo „?“ při chudých podkladech `evidence: thin`, čárkovaně podtržený);
- % kroků `steps.percent`;
- riziko jen mimo `standard`: „!“ zvýšené, „!!“ kritické.

Titulek nese celý popis: kroky done/total, % DoD (`dod.percent`), riziko s důvody, model a poradce.

- `logic/card-gauge-badge.ts`: `gaugeBadge(gauge)` → model odznaku nebo `null` (chybějící nebo neplatné `gauge`
  se nekreslí, nic se neodhaduje). Test `card-gauge-badge.test.ts`.
- `components/CardGaugeBadge.tsx`: jen kreslí model, klik patří pilulce. Test `CardGaugeBadge.test.ts`.
- `styles/card-gauge-badge.css`: blok `card-gauge`.

Model počítá `velinPills` (`../logic/velin-model.ts`, pole `gauge` pilulky), kreslí ho `VelinLayer`.
