// Dílek Ikona menu: ikona lišty ze sady `ui-kit/icon`, nebo jedna ze dvou vlastních značek menu —
// tři vodorovné čáry (☰) a posuvníky Nastavení. Kreslí se stejnou stopou 1.75 px a `currentColor`
// jako sada, aby lišta ikon vypadala jako jedna rodina. Nic neví o stavu; dostane jméno a nakreslí.
import Icon from "@/ui-kit/icon/components/Icon";
import type { DockIconName } from "@/layout/panel-dock/logic/panel-dock";

/** Vlastní značky menu (tvary podle Lucide, licence ISC). */
const OWN: Record<"menu" | "settings", string> = {
  menu: "M4 6h16 M4 12h16 M4 18h16",
  settings: "M21 4h-7 M10 4H3 M21 12h-9 M8 12H3 M21 20h-5 M12 20H3 M14 2v4 M8 10v4 M16 18v4",
};

export default function DockIcon({ name, size = 20 }: { name: DockIconName; size?: 16 | 20 }) {
  if (name !== "menu" && name !== "settings") return <Icon name={name} size={size} />;
  return (
    <svg
      className={"icon icon--" + size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      aria-hidden
    >
      <path d={OWN[name]} />
    </svg>
  );
}
