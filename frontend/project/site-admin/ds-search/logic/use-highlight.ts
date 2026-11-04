// Zvýraznění výsledku hledání: po přepnutí sekce najde řádek podle `data-testid`, posune ho doprostřed a na chvíli
// ho rozsvítí třídou `ds-search__hit`. Sekce se vykreslí až po přepnutí, proto se hledá v dalším snímku.
import { useEffect } from "react";

export const HIT_CLASS = "ds-search__hit";

export function useHighlight(target: string, stamp: number) {
  useEffect(() => {
    if (!target) return;
    let timer = 0;
    const frame = requestAnimationFrame(() => {
      const element = document.querySelector(`[data-testid="${CSS.escape(target)}"]`);
      if (!element) return;
      element.scrollIntoView({ block: "center", behavior: "smooth" });
      element.classList.add(HIT_CLASS);
      timer = window.setTimeout(() => element.classList.remove(HIT_CLASS), 2400);
    });
    return () => { cancelAnimationFrame(frame); window.clearTimeout(timer); };
  }, [target, stamp]);
}
