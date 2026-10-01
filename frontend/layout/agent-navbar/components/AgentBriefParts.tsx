// Stavební kameny zadání karty: rámeček sekce, dvojice klíč–hodnota, odškrtnutá položka a soused
// s předávkou. Jsou to čtyři malé dílky, které `AgentBriefSections` skládá — samy nevědí nic
// o balíčku pro model, dostanou hotový text a nakreslí ho. Nic z toho není ovládání: zadání se mění
// v kartě, v inspektoru, ne v polici.
//
// Všechny značky jsou kreslené ikony ze sady `ui-kit/icon`, ne Unicode znaky: kolečko a fajfka
// u odškrtnutí, šipka u předávky (nahoru = rodič, doleva = přichází, doprava = odchází). Glyfy
// (✓ ○ ▲ ← →) se v každém systému kreslily jinou tloušťkou a v úzkém sloupci se rozpadaly.
import type { ReactNode } from "react";
import Icon from "@/ui-kit/icon/components/Icon";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";
import type { AgentCategory } from "@/editor/component-library/agent-catalog/logic/agent-catalog";

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
  /** Kategorie katalogu, jejíž barvu hlavička půjčí — je to jen barevný jazyk, sekce žádnou položku katalogu nenese. */
  category: AgentCategory;
  /** Ikona sekce: kreslí, o čem sekce je (terč = cíl, čip = harness, smyčka, šipky = předávky, složka = prostor). */
  icon: IconName;
  /** Tiché číslo vpravo v hlavičce, např. „2/4 splněno“; prázdné se nezobrazí. */
  meta?: string;
  empty?: boolean;
  children?: ReactNode;
}) {
  return (
    <section className={"agent-navbar__section agent-navbar__section--" + category}>
      <header className="agent-navbar__section-head">
        <span className="agent-navbar__section-icon">
          <Icon name={icon} size={16} />
        </span>
        <h4 className="agent-navbar__section-title">{title}</h4>
        {meta && <span className="agent-navbar__section-meta">{meta}</span>}
      </header>
      <div className="agent-navbar__section-body">
        {empty ? <p className="agent-navbar__section-empty">Karta tu nic nemá.</p> : children}
      </div>
    </section>
  );
}

/** Dvojice klíč–hodnota na jednom řádku: parametr akce, počet bloků, počet dětí. */
export function Kv({ label, value }: { label: string; value: string }) {
  return (
    <p className="agent-navbar__kv">
      <span className="agent-navbar__kv-key">{label}</span>
      <span className="agent-navbar__kv-value">{value}</span>
    </p>
  );
}

/** Odškrtnutá položka: kritérium konce i krok harnessu. Je to obraz stavu, ne ovládání — proto ne checkbox. */
export function Check({ text, checked }: { text: string; checked: boolean }) {
  return (
    <li className={"agent-navbar__check" + (checked ? " agent-navbar__check--done" : "")}>
      <Icon
        className="agent-navbar__check-box"
        name={checked ? "check" : "circle"}
        size={16}
        label={checked ? "Splněno" : "Nesplněno"}
      />
      <span className="agent-navbar__check-text">{text}</span>
    </li>
  );
}

/** Soused nebo rodič: šipka podle směru předávky, jméno tučně a pod ním první věta jeho předávky. */
export function Hand({ icon, name, handoff }: { icon: IconName; name: string; handoff: string }) {
  return (
    <li className="agent-navbar__hand">
      <span className="agent-navbar__hand-name">
        <Icon className="agent-navbar__hand-arrow" name={icon} size={16} />
        {name}
      </span>
      <span className="agent-navbar__hand-text">{handoff || "bez předávky"}</span>
    </li>
  );
}
