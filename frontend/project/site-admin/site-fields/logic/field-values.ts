// Hodnoty polí Vzhledu a Tlačítek, jak je posílá server: barva je hex, funkce nebo alias `{token}`, délka text.
// Náhled je píše do CSS stránky OPORY, proto hodnota se znaky, které by ukončily deklaraci nebo pravidlo, do CSS
// nikdy nejde (server ji při uložení stejně zahodí s poznámkou).
import { parseColor, toHex } from "@/project/site-admin/ds-colors/logic/color-contrast";

const ALIAS = /^\{([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\}$/;

/** Hodnota bezpečná pro deklaraci CSS náhledu, jinak `null`. */
export function safeCss(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  const text = String(value).trim();
  return text && !/[;{}<>\\]|\/\*/.test(text) ? text : null;
}

/** Hodnota pro CSS: alias `{token}` → `var(--token)` (tečka escapovaná jako v serveru), jinak beze změny. */
export function cssValue(value: unknown): string | null {
  const text = safeCss(value);
  if (!text) return null;
  const alias = text.match(ALIAS);
  return alias ? `var(--${alias[1].replace(/\./g, "\\.")})` : text;
}

/** Barva pro `<input type="color">`: jen literál, který jde přečíst; alias a průhledná nemají výběr. */
export function pickerHex(value: string): string | null {
  if (!value || ALIAS.test(value.trim())) return null;
  const rgb = parseColor(value.trim());
  return rgb ? toHex(rgb) : null;
}

/** Text z pole formuláře → hodnota pro dokument: prázdné = nenastaveno. */
export const fieldValue = (text: string): string | null => text.trim() ? text.trim() : null;
