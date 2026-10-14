// Stavební kameny zadání karty: rámeček sekce, dvojice klíč–hodnota, odškrtnutá položka a soused
// s předávkou. Jsou to čtyři malé dílky, které `CardBriefSections` skládá — samy nevědí nic
// o balíčku pro model, dostanou hotový text a nakreslí ho. Nic z toho není ovládání: zadání se mění
// v kartě, v inspektoru, ne v polici.
//
// Všechny značky jsou kreslené ikony ze sady `ui-kit/icon`, ne Unicode znaky: kolečko a fajfka
// u odškrtnutí, šipka u předávky (nahoru = rodič, doleva = přichází, doprava = odchází). Glyfy
// (✓ ○ ▲ ← →) se v každém systému kreslily jinou tloušťkou a v úzkém sloupci se rozpadaly.
import type { ReactNode } from "react";
import Icon from "@/ui-kit/icon/components/Icon";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";

/** Barevný tón sekce: půjčuje si barvu kategorií postupů z tokenů (`--cat-<tón>`), nic víc. */
export type SectionTone = "workflows" | "pipelines" | "rules" | "hooks" | "agents";

/** Jedna sekce: rámeček s hlavičkou (žeton, název, tiché číslo) a tělem, nebo tichá věta, když karta v téhle části nic nemá. */
export function Section({
  title,
  category,
  icon,
  meta,
  empty,
  children,
}: {
  title: string;
  /** Tón, jehož barvu hlavička půjčí — je to jen barevný jazyk, sekce žádnou položku katalogu nenese. */
  category: SectionTone;
  /** Ikona sekce: kreslí, o čem sekce je (terč = cíl, čip = harness, smyčka, šipky = předávky, složka = prostor). */
  icon: IconName;
  /** Tiché číslo vpravo v hlavičce, např. „2/4 splněno“; prázdné se nezobrazí. */
  meta?: string;
  empty?: boolean;
  children?: ReactNode;
}) {
  return (
    <section className={"card-brief__section card-brief__section--" + category}>
      <header className="card-brief__section-head">
        <span className="card-brief__section-icon">
          <Icon name={icon} size={16} />
        </span>
        <h4 className="card-brief__section-title">{title}</h4>
        {meta && <span className="card-brief__section-meta">{meta}</span>}
      </header>
      <div className="card-brief__section-body">
        {empty ? <p className="card-brief__section-empty">Karta tu nic nemá.</p> : children}
      </div>
    </section>
  );
}

/** Dvojice klíč–hodnota na jednom řádku: parametr akce, počet bloků, počet dětí. */
export function Kv({ label, value }: { label: string; value: string }) {
  return (
    <p className="card-brief__kv">
      <span className="card-brief__kv-key">{label}</span>
      <span className="card-brief__kv-value">{value}</span>
    </p>
  );
}

/** Odškrtnutá položka: kritérium konce i krok harnessu. Je to obraz stavu, ne ovládání — proto ne checkbox. */
export function Check({ text, checked }: { text: string; checked: boolean }) {
  return (
    <li className={"card-brief__check" + (checked ? " card-brief__check--done" : "")}>
      <Icon
        className="card-brief__check-box"
        name={checked ? "check" : "circle"}
        size={16}
        label={checked ? "Splněno" : "Nesplněno"}
      />
      <span className="card-brief__check-text">{text}</span>
    </li>
  );
}

/** Soused nebo rodič: šipka podle směru předávky, jméno tučně a pod ním první věta jeho předávky. */
export function Hand({ icon, name, handoff }: { icon: IconName; name: string; handoff: string }) {
  return (
    <li className="card-brief__hand">
      <span className="card-brief__hand-name">
        <Icon className="card-brief__hand-arrow" name={icon} size={16} />
        {name}
      </span>
      <span className="card-brief__hand-text">{handoff || "bez předávky"}</span>
    </li>
  );
}
