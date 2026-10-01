// Dílek Ikona: jeden `<svg>` s jednou cestou. Nic neví o panelech ani o datech — dostane jméno
// ikony a velikost a nakreslí ji. Barvu nevolí: kreslí `currentColor`, takže si ji vezme z místa,
// kam je ikona vložená (žeton kategorie, tlačítko lišty, tichý řádek). Neznámé jméno nakreslí
// prázdné plátno, ne výjimku — rozhraní se kvůli ikoně nikdy nerozbije.
//
// Přístupnost: ikona je ve výchozím stavu ozdoba vedle popisku (`aria-hidden`), protože popisek
// už to slovo říká. Když ikona stojí sama za sebe (tlačítko bez textu), předá se `label` a z ikony
// se stane obrázek se jménem (`role="img"` + `aria-label`).
import { iconPath, type IconName } from "@/ui-kit/icon/logic/icon-paths";
import "@/ui-kit/icon/styles/icon.css";

/** Trojí velikost celé aplikace: 16 do řádku a žetonu, 20 do lišty, 24 tam, kde ikona stojí sama. */
export type IconSize = 16 | 20 | 24;

export default function Icon({
  name,
  size = 20,
  className,
  label,
}: {
  name: IconName;
  size?: IconSize;
  /** Třída okolí (barva, poloha); dílek si k ní přidá vlastní `icon` a velikost. */
  className?: string;
  /** Jméno pro odečítač obrazovky. Bez něj je ikona ozdoba vedle textu a odečítač ji přeskočí. */
  label?: string;
}) {
  const d = iconPath(name);
  return (
    <svg
      className={["icon", "icon--" + size, className].filter(Boolean).join(" ")}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
    >
      {d ? <path d={d} /> : null}
    </svg>
  );
}
