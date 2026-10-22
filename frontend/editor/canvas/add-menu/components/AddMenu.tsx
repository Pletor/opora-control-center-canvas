// Jediné „+ Přidat“ lišty Editoru (návrh „Opora Editor — lean“, rám 1b): Sektor, Uzel, Komentář, Oblast.
// Dílek jen nabídne volbu; tvorbu (dialog sektoru a uzlu, nový komentář či oblast) dělá rodič.
import ToolbarMenu from "@/ui-kit/toolbar-menu/components/ToolbarMenu";

export type AddKind = "sector" | "node" | "comment" | "area";
const ITEMS: { key: AddKind; label: string; glyph: string; hint: string }[] = [
  { key: "sector", label: "Sektor", glyph: "▭", hint: "Sektor seskupí karty jedné části práce." },
  { key: "node", label: "Uzel", glyph: "□", hint: "Karta práce pro agenta nebo člověka." },
  { key: "comment", label: "Komentář", glyph: "❝", hint: "Lístek s poznámkou na plátně." },
  { key: "area", label: "Oblast", glyph: "⬚", hint: "Rámeček, který vizuálně sdruží karty." },
];

export default function AddMenu({ disabled, onAdd }: { disabled: boolean; onAdd: (kind: AddKind) => void }) {
  return <ToolbarMenu label="+ Přidat ▾" title="Přidat na plátno" align="end" disabled={disabled}
    items={ITEMS} onSelect={(key) => onAdd(key as AddKind)} />;
}
