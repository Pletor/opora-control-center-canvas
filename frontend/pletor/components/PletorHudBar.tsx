import { useEffect, useState, type ReactNode } from "react";

/** Okamžik načtení aplikace: uptime kokpitu běží od startu OPORY, ne od posledního otevření HUD. */
const STARTED = Date.now();
const pad = (n: number) => String(n).padStart(2, "0");

function uptime(now: number): string {
  const s = Math.max(0, Math.floor((now - STARTED) / 1000));
  const h = Math.floor(s / 3600);
  return h ? `${h}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}` : `${pad(Math.floor(s / 60))}:${pad(s % 60)}`;
}

/** Horní lišta kokpitu: značka, čas, uptime, stav srdce, přepínač Poslech (`children`) a vstup do OPORY (HUD se složí do okna). */
export default function PletorHudBar({ heart, onEnter, children }: { heart: string; onEnter: () => void; children?: ReactNode }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const time = new Date(now);
  return (
    <header className="pletor-hud__bar">
      <strong className="pletor-hud__brand">PLETOR<small className="pletor-hud__brand-sub">nad srdcem OPORY</small></strong>
      <span className="pletor-hud__stat">čas <b>{pad(time.getHours())}:{pad(time.getMinutes())}:{pad(time.getSeconds())}</b></span>
      <span className="pletor-hud__stat">uptime <b>{uptime(now)}</b></span>
      <span className="pletor-hud__stat" role="status"><i className="pletor-hud__dot" aria-hidden="true" />srdce <b>{heart}</b></span>
      {children}
      <button type="button" className="pletor-hud__button" onClick={onEnter} title="Složit Pletora do okna (Esc)">Vstoupit do OPORY</button>
    </header>
  );
}
