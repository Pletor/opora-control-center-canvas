# Pole nastavení webu

Společná pole editorů Vzhled (`../site-appearance/`) a Tlačítka (`../site-buttons/`) podle `image.png`: popisek nad polem, mřížka po třech.

- `components/Fields.tsx`: `Field`, `TextField`, `SelectField`, `ColorField` (vzorek s výběrem, text, nabídka aliasů `{token}`), `Segments` (zaoblení, šířka). Prázdné pole = nenastaveno, `placeholder` ukazuje zděděnou hodnotu. Pole hlásí text nahoru, nic neukládá.
- `logic/field-values.ts` (+ test): `safeCss` (hodnota, která nemůže ukončit deklaraci náhledu), `cssValue` (alias → `var(--token)` jako server), `pickerHex`, `fieldValue`.
