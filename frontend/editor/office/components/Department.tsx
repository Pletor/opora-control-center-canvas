// Oddělení: vodorovné pásmo oblasti s jejím názvem a barvou rámečku z plátna; uvnitř místnosti.
// Hala (sektory mimo oblast) je totéž pásmo bez barvy.
import type { ReactNode } from "react";
import type { AreaColor } from "@/shared/types/logic/types";

type Props = { name: string; color: AreaColor | null; empty: boolean; children: ReactNode };

export default function Department({ name, color, empty, children }: Props) {
  return (
    <section className={"office-department" + (color ? "" : " office-department--hall")} data-color={color ?? undefined} aria-label={"Oddělení " + name}>
      <h3 className="office-department__name">{name}</h3>
      {empty ? <p className="office-department__empty">Oddělení zatím nemá místnosti.</p> : <div className="office-department__rooms">{children}</div>}
    </section>
  );
}
