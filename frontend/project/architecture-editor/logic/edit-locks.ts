// Proč je úprava v editoru architektury zakázaná (docs/domeny-a-worktree.md §4, §10 `DomainLockNote`).
// Struktura (domény a stránky) a obsah stránky (karty, sektory, oblasti) mají vlastní zámek:
// na Git mainu je architektura zapisovatelná, obsah jen pro čtení. Zámek je věta pro člověka,
// nikdy jen zašednuté tlačítko; `transient` = přejde sám (ukládání, načítání).

export type EditLock = { text: string; transient: boolean } | null;

export type LockInput = {
  /** Pohled je načtený. */
  loaded: boolean;
  /** Chyba posledního čtení nebo zápisu. */
  loadError: string;
  /** Editor zpracoval adresu (doména, stránka). */
  ready: boolean;
  busy: boolean;
  loading: boolean;
  removing: boolean;
  removalOpen: boolean;
  scopeError: string;
  /** `view.architectureEditable`; starší backend bez pole = `!readOnly`. */
  architectureEditable: boolean;
  /** `view.readOnly`: obsah prostoru (main). */
  readOnly: boolean;
  desktopLoading: boolean;
  desktopError: string;
  desktopReadOnly: boolean;
  /** Otevřená doména, stránka nebo jejich předek je uzavřená karta. */
  scopeClosed: boolean;
};

const lock = (text: string, transient = false): EditLock => ({ text, transient });

/** Společné důvody: načítání, ukládání, rozpracované odstranění, neplatná adresa. */
function baseLock(input: LockInput): EditLock {
  if (!input.loaded && input.loadError) return lock(`Architekturu se nepodařilo načíst: ${input.loadError} Zkuste Obnovit.`);
  if (!input.loaded || !input.ready || input.loading) return lock("Načítám architekturu…", true);
  if (input.busy) return lock("Ukládám změnu…", true);
  if (input.removing) return lock("Odstraňuji…", true);
  if (input.removalOpen) return lock("Nejdřív potvrďte nebo zrušte odstranění.");
  if (input.scopeError) return lock(`Otevřená část neplatí: ${input.scopeError}`);
  return null;
}

/** Stav karet určuje uzavření; bez něj nejde ověřit, jestli se smí měnit. */
function cardLock(input: LockInput): EditLock {
  if (input.desktopLoading) return lock("Načítám stav karet…", true);
  if (input.desktopError) return lock(`Stav karet se nepodařilo načíst, uzavření nelze ověřit: ${input.desktopError}`);
  if (input.scopeClosed) return lock("Otevřená karta nebo její předek je uzavřená (potvrzené hotovo). Pro úpravy ji nejdřív otevřete v Editoru.");
  return null;
}

/** Domény a stránky: zapisovatelné i na mainu, když to backend dovolí. */
export function structureLock(input: LockInput): EditLock {
  return baseLock(input)
    ?? (input.architectureEditable ? null : lock("Architekturu v tomto pracovním prostoru nelze upravovat."))
    ?? cardLock(input);
}

/** Obsah stránky (vložení, přesun, vazby, oblasti, sektory): jen v zapisovatelném prostoru. */
export function contentLock(input: LockInput): EditLock {
  return baseLock(input)
    ?? (input.readOnly || input.desktopReadOnly ? lock("Obsah stránek je v tomto prostoru jen pro čtení (main). Karty a sektory upravujte ve worktree domény; domény a stránky jdou měnit i odsud.") : null)
    ?? cardLock(input);
}

/** Architektura zapisovatelná podle pohledu; starší pohled bez pole se řídí `readOnly`. */
export function architectureEditable(view: { readOnly: boolean; architectureEditable?: boolean } | null): boolean {
  if (!view) return false;
  return view.architectureEditable ?? !view.readOnly;
}
