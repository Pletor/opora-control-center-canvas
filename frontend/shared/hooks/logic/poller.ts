// Jeden vzor pro všechna periodická čtení UI (karta P1 Výkon). Server je jeden worker a dlouhé dotazy
// drží globální zámek: `setInterval` posílal nový dotaz, i když předchozí ještě běžel, a každé skryté
// okno pollovalo dál. Poller proto: (1) nikdy nespustí dotaz, dokud běží předchozí (požadavek během
// běhu se provede jednou hned po něm), (2) další kolo plánuje až po dokončení, (3) ve skryté záložce
// stojí a po návratu udělá jeden refresh. Bez Reactu; hook `usePolling` ho jen napojí na komponentu.

type Timer = ReturnType<typeof setTimeout>;

/** Zdroj viditelnosti stránky; výchozí je `document.hidden` + `visibilitychange`. */
export type VisibilitySource = { hidden: () => boolean; subscribe: (listener: () => void) => () => void };

export type PollerOptions = {
  run: () => Promise<unknown>;
  /** Pauza mezi koncem jednoho dotazu a začátkem dalšího (ms); 0 = jen ruční `refresh`. */
  intervalMs: number;
  /** Načíst hned při `start` (výchozí ano); `false` = první dotaz až po intervalu. */
  immediate?: boolean;
  visibility?: VisibilitySource;
  setTimer?: (fn: () => void, ms: number) => Timer;
  clearTimer?: (timer: Timer) => void;
};

export type Poller = {
  /** Rozběhne kola; `load` přepíše `immediate` pro tento start. */
  start: (load?: boolean) => void; stop: () => void;
  /** Načíst teď; když dotaz běží, provede se jednou hned po něm. */
  refresh: () => Promise<void>;
  /** Načíst teď, jen když nic neběží (návrat do okna: běžící dotaz už je čerstvý). */
  poke: () => Promise<void>;
  running: () => boolean;
};

export const documentVisibility: VisibilitySource = {
  hidden: () => typeof document !== "undefined" && document.hidden,
  subscribe: (listener) => {
    if (typeof document === "undefined") return () => {};
    document.addEventListener("visibilitychange", listener);
    return () => document.removeEventListener("visibilitychange", listener);
  },
};

export function createPoller(options: PollerOptions): Poller {
  const { run, intervalMs, immediate = true, visibility = documentVisibility } = options;
  const setTimer = options.setTimer ?? ((fn, ms) => setTimeout(fn, ms));
  const clearTimer = options.clearTimer ?? ((timer) => clearTimeout(timer));
  let timer: Timer | undefined;
  let inflight: Promise<void> | undefined;
  let again = false;
  let stopped = true;
  // Kolo propadlo ve skryté záložce: po návratu se načte jednou hned.
  let stale = false;
  let unsubscribe = () => {};

  function cancel() {
    if (timer !== undefined) clearTimer(timer);
    timer = undefined;
  }

  function schedule() {
    cancel();
    if (stopped || intervalMs <= 0) return;
    if (visibility.hidden()) { stale = true; return; }
    timer = setTimer(() => {
      timer = undefined;
      if (visibility.hidden()) stale = true;
      else void refresh();
    }, intervalMs);
  }

  // Ruční refresh funguje i u zastaveného polleru (sdílený zdroj po vlastním zápisu); zastavený
  // poller jen neplánuje další kola a nesleduje viditelnost.
  function refresh(): Promise<void> {
    if (inflight) { again = true; return inflight; }
    cancel();
    stale = false;
    // Dotaz odchází synchronně (odběratel vidí běžící načtení hned); chyby řeší `run`, poller jede dál.
    let started: Promise<unknown>;
    try { started = run(); } catch (error) { started = Promise.reject(error); }
    inflight = Promise.resolve(started)
      .then(() => undefined, () => undefined)
      .finally(() => {
        inflight = undefined;
        if (again) { again = false; void refresh(); } else schedule();
      });
    return inflight;
  }

  function changed() {
    if (stopped) return;
    if (visibility.hidden()) { cancel(); if (!inflight) stale = true; return; }
    if (stale && !inflight) void refresh();
  }

  return {
    start(load = immediate) {
      if (!stopped) return;
      stopped = false;
      unsubscribe = visibility.subscribe(changed);
      if (!load) { if (!inflight) schedule(); }
      else if (visibility.hidden()) stale = true;
      // Běžící dotaz (ruční refresh před startem) je čerstvý; po něm se kolo naplánuje samo.
      else if (!inflight) void refresh();
    },
    stop() {
      stopped = true;
      again = false;
      stale = false;
      cancel();
      unsubscribe();
      unsubscribe = () => {};
    },
    refresh,
    poke: () => inflight ?? refresh(),
    running: () => inflight !== undefined,
  };
}
