/** Jeden řádek pod hlavičkou: co dělá srdce a kolik eskalací čeká na člověka. */
export default function PletorHeartLine({ heart, escalations }: { heart: string; escalations: string }) {
  return <p className="pletor__heart" role="status">Srdce: {heart} · {escalations}</p>;
}
