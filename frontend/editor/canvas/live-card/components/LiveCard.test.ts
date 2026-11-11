import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LIVE_CARD_BARE, LIVE_CARD_FULL } from "../logic/live-card-fixture";
import CardHead from "./CardHead";
import HumanSide from "./HumanSide";
import AgentSide from "./AgentSide";
import CardFoot from "./CardFoot";

const html = (type: unknown, props: object) => renderToStaticMarkup(createElement(type as never, props as never));
const noop = () => {};

describe("live card face", () => {
  it("draws every section of a full card with real data", () => {
    const out = html(HumanSide, { card: LIVE_CARD_FULL, recent: LIVE_CARD_FULL.recent, onOpenCard: noop });
    expect(out).toContain("live-card__ports");
    expect(out).toContain("Přístup člena");
    expect(out).toContain("live-card__port--code");
    expect(out).not.toContain("staví se F1");
    expect(out).not.toContain("staví se F4");
    // Budoucnost: verdikt slovem, větev → cíl, konflikt červeně, dopad přes vazbu a překryv s jiným úkolem.
    expect(out).toContain('data-oh-future="blocked"');
    expect(out).toContain("OP-1 → main · 2 soubory");
    expect(out).toMatch(/live-card__item--bad[^>]*><b class="live-card__mark">✕<\/b><span class="live-card__item-text">konflikt backend\/api\/fapi.py/);
    expect(out).toContain("Přístup člena (používá)");
    expect(out).toContain("OP-2 mění totéž · backend/fapi_sig.py");
    expect(out).toContain("1/2");
    // Zrcadlo: shoda fixou se soubor:řádek, chybějící kroužek, navíc červeně, pruh shoda/(shoda+chybí).
    expect(out).toMatch(/live-card__ink">POST \/api\/fapi\/webhook<\/span><br\/><span class="live-card__code">backend\/api\/fapi.py:12</);
    expect(out).toContain("backend/fapi_sig.py<");
    expect(out).toMatch(/live-card__item--miss[^>]*><b class="live-card__mark">○/);
    expect(out).toContain("src/marketing/Popup.tsx · navíc");
    expect(out).toContain("2/3");
    expect(out).toContain("9b10d44<");
    expect(out).toContain("Tok dat");
    expect(out).toContain("náhled running");
    expect(out).toContain("PR #412");
    expect(out).toContain("live-card__spark");
    expect(out).toContain("Deník karty");
    expect(out).toContain("Rozhodnutí a výzkum");
    expect(out).toContain("Webhook endpoint");
  });
  it("skips null and empty sections, shows only the pending truths", () => {
    const out = html(HumanSide, { card: LIVE_CARD_BARE, recent: [], onOpenCard: noop });
    for (const absent of ["live-card__ports", "Budoucnost", "Záměr", "Skutečnost", "Tok dat", "Výstup", "Linie", "live-card__spark", "Deník", "Rozhodnutí", "Uvnitř"]) expect(out).not.toContain(absent);
    expect(out).toContain("staví se F1");
  });
  it("head carries ring, counters and the side switch next to close", () => {
    const out = html(CardHead, { card: LIVE_CARD_FULL, nodeId: "pay", side: "agent", onSide: noop, onClose: noop });
    expect(out).toContain("72 %");
    expect(out).toContain("6/6");
    expect(out).toContain("0,16");
    expect(out).toMatch(/aria-pressed="true"[^>]*>Pro agenty/);
    expect(out).toContain('aria-label="Zavřít"');
    expect(html(CardHead, { card: null, nodeId: "pay", side: "human", onSide: noop, onClose: noop })).toContain("pay");
  });
  it("footer offers only real actions", () => {
    const withHeart = html(CardFoot, { card: LIVE_CARD_FULL, busy: false, onPanel: noop, onRefresh: noop, onAskHeart: async () => true });
    expect(withHeart).toContain("Další krok: doplnit member_id");
    expect(withHeart).toContain("Zeptat se srdce");
    expect(withHeart).toContain('href="http://127.0.0.1:8812"');
    expect(withHeart).toContain("Pracovní panel");
    const bare = html(CardFoot, { card: LIVE_CARD_BARE, busy: false, onPanel: noop, onRefresh: noop });
    expect(bare).not.toContain("Zeptat se srdce");
    expect(bare).not.toContain("Otevřít náhled");
    expect(bare).not.toContain("Otevřít vnitřní plátno");
    expect(html(CardFoot, { card: LIVE_CARD_BARE, busy: false, onPanel: noop, onRefresh: noop, onEnterCanvas: noop })).toContain("Otevřít vnitřní plátno");
    expect(bare).toContain("Pracovní panel");
    // Předat do Kanceláře jen karta bez úkolu Linie.
    expect(bare).toContain("Předat do Kanceláře");
    expect(withHeart).not.toContain("Předat do Kanceláře");
  });
});

describe("live card back", () => {
  it("shows address, layered JSON, reads, writes, triggers, tools and the work panel", () => {
    const out = html(AgentSide, { nodeId: "pay", mark: "OP-1", agent: LIVE_CARD_FULL.agent, souhrn: { id: "OP-1", progress: 72 }, tvar: { criteria: [] },
      briefError: "", raw: [], onPanel: noop, onCopy: noop });
    expect(out).toContain("opora://card/OP-1");
    expect(out).toContain("worker:codex-3");
    expect(out).toContain('<span class="live-card__json-key">&quot;progress&quot;</span>');
    expect(out).toContain("live-card__method--sse");
    expect(out).toContain("/api/desktop-v3/agent-output");
    expect(out).toContain("commit s Opora-Mark");
    expect(out).toContain("trace --mark OP-1");
    expect(out).toContain("Pracovní panel");
  });
  it("works without agent data from an older server", () => {
    const out = html(AgentSide, { nodeId: "pay", mark: null, agent: null, souhrn: null, tvar: null, briefError: "", raw: [], onPanel: noop, onCopy: noop });
    expect(out).toContain("opora://card/pay");
    expect(out).not.toContain("trace --mark");
    expect(out).not.toContain("Čtení po vrstvách");
  });
});
