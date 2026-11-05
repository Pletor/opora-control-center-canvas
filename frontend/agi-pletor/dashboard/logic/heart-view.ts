import { list, rec, str, unavailable } from "./view-common";

export type Card = { id: string; title: string; value: string };
export type HeartView = { cards: Card[]; queue: { workspace: string; pending: string }[]; batches: { at: string; status: string; summary: string; cost: string }[]; problem: string };

const yesNo = (flag: unknown) => (flag === true ? "ano" : "ne");

/** Odpověď `GET /api/pletor/heart` → karty stavu, fronta a posledních 20 dávek; chybějící pole jsou prázdná. */
export function heartView(raw: unknown): HeartView {
  const root = rec(raw);
  const status = rec(root.status);
  const brain = rec(root.brain);
  const problems = ["status", "queue", "batches", "brain"].map((key) => unavailable(root[key])).filter(Boolean);
  const sleeping = status.sleeping === true ? `spí${str(status.sleepingUntil) ? " do " + str(status.sleepingUntil) : ""}` : "ne";
  const cards: Card[] = [
    { id: "bezi", title: "Běží", value: yesNo(status.running) },
    { id: "ceka", title: "Čeká", value: str(status.pending) || "0" },
    { id: "spi", title: "Spí", value: sleeping },
    { id: "chyba", title: "Chyba", value: str(status.error) || "—" },
    { id: "brana", title: "Brána zapnutá", value: yesNo(root.gate) },
    { id: "verze", title: "Verze promptu srdce", value: str(brain.version) || "—" },
  ];
  const queue = list(root.queue).map((item) => ({ workspace: str(rec(item).workspace), pending: str(rec(item).pending) || "0" }));
  const batches = list(root.batches).slice(-20).map((item) => {
    const batch = rec(item);
    const cost = typeof batch.costUsd === "number" ? `${batch.costUsd.toFixed(3)} USD` : "—";
    const state = str(batch.status) || (batch.ok === true ? "ok" : batch.ok === false ? "chyba" : "—");
    return { at: str(batch.finishedAt) || str(batch.startedAt) || str(batch.at) || "—", status: state, summary: str(batch.summary), cost };
  });
  return { cards, queue, batches, problem: problems.join(" · ") };
}
