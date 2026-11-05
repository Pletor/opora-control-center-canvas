import { useState } from "react";
import { ENTRY_LINKS } from "../logic/entry-route";
import PletorHudCanvas from "@/pletor/components/PletorHudCanvas";
import "@/pletor/styles/pletor.css";
import "../styles/intro.css";

/** The entry is independent of project data and never activates a microphone or model. */
export default function Intro() {
  const [paused, setPaused] = useState(false);
  return <main className={`intro${paused ? " intro--paused" : ""}`}>
    <header className="intro__header">
      <a className="intro__brand" href="/?screen=intro" aria-label="Opora — úvod"><span className="intro__mark" aria-hidden="true">O</span><span>OPORA<small className="intro__brand-detail">CONTROL CENTER</small></span></a>
      <button className="intro__motion" type="button" aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? "Spustit animaci" : "Pozastavit animaci"}<span aria-hidden="true">{paused ? "▷" : "Ⅱ"}</span></button>
    </header>
    <section className="intro__hero" aria-labelledby="intro-title">
      <div className="intro__universe" aria-hidden="true">
        <PletorHudCanvas state="idle" level={() => null} paused={paused} className="intro__canvas" />
        <span className="intro__coordinate intro__coordinate--left">PLETOR<br/>VAŠE MYŠLENKY</span><span className="intro__coordinate intro__coordinate--right">SRDCE<br/>CESTA K REALIZACI</span>
      </div>
      <p className="intro__eyebrow">ČLOVĚK DÁVÁ SMĚR. OPORA POMÁHÁ TVOŘIT.</p>
      <h1 id="intro-title">Váš směr.<br/><em>Společná inteligence.</em></h1>
      <p className="intro__lead">Sdílejte ji s Pletorem. Společně najdete další krok.</p>
    </section>
    <nav className="intro__entries" aria-label="Vstoupit do Opory">
      {ENTRY_LINKS.map((entry) => <a className={`intro__entry intro__entry--${entry.id}`} key={entry.id} href={entry.href}>
        <div className="intro__entry-top"><span>{entry.number} / {entry.label}</span><span className="intro__arrow" aria-hidden="true">↗</span></div>
        <h2>{entry.title}</h2><p>{entry.description}</p><span className="intro__action">{entry.action}<span aria-hidden="true"> →</span></span>
      </a>)}
    </nav>
    <footer className="intro__footer"><span>Váš směr. Společná inteligence.</span><span>PLETOR <span aria-hidden="true">·</span> SRDCE <span aria-hidden="true">·</span> OPORA</span></footer>
  </main>;
}
