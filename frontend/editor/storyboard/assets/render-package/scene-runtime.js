// Runtime webové scény (animation: "scena"): jeden zdroj pro editor (srcdoc iframe) i render balíčku (index.html).
// sceneDocument(html) ho vloží jako první <script> do <head>, takže běží dřív než scéna. Čas řídí jen host:
// window.seek(t) spočítá stav momentů, zapíše ho jako CSS proměnné na <html>, zavolá window.scene.seek(t, state),
// pozastaví každou CSS animaci a přechod na (t - t0) a schová vypnuté vrstvy. Žádné časovače.
// Editor mluví přes postMessage ({type: "board" | "seek"} → {type: "ready" | "error"}); render.py vloží
// window.STORYBOARD_DATA a volá window.seek(t) přímo.
(function () {
  "use strict";
  var NO_SEEK = "Scéna nedefinuje window.scene.seek(t, state).";
  var EASES = {
    linear: function (u) { return u; },
    in: function (u) { return u * u; },
    out: function (u) { return 1 - (1 - u) * (1 - u); },
    inout: function (u) { return u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2; },
    hold: function () { return 0; },
  };
  var HEX = /^#[0-9a-f]{6}$/i;
  function lerp(a, b, u) { return a + (b - a) * u; }
  function lerpColor(a, b, u) {
    var ca = parseInt(a.slice(1), 16), cb = parseInt(b.slice(1), 16);
    function ch(shift) { return Math.round(lerp((ca >> shift) & 255, (cb >> shift) & 255, u)).toString(16).padStart(2, "0"); }
    return "#" + ch(16) + ch(8) + ch(0);
  }
  // Stav v čase t: mezi momenty a→b podle ease momentu a; čísla a barvy se míchají, ostatní drží stav a (jako stateAt).
  function stateAt(board, t) {
    var ms = (board && board.moments) || [];
    if (!ms.length) return {};
    var i = 0, u = 0;
    if (t > ms[0].t) {
      i = ms.length - 1; u = 1;
      for (var k = 0; k < ms.length - 1; k++) if (t < ms[k + 1].t) { i = k; u = (t - ms[k].t) / (ms[k + 1].t - ms[k].t); break; }
    }
    var a = ms[i], b = ms[i + 1];
    var out = Object.assign({}, a.state);
    if (!b || u === 0) return out;
    var e = (EASES[a.ease] || EASES.linear)(u);
    Object.keys(a.state).forEach(function (key) {
      var x = a.state[key], y = b.state[key];
      if (typeof x === "number" && typeof y === "number") out[key] = lerp(x, y, e);
      else if (typeof x === "string" && typeof y === "string" && HEX.test(x) && HEX.test(y)) out[key] = lerpColor(x, y, e);
    });
    return out;
  }

  var hidden = [];
  var hiddenStyle = null;
  var ready = false;
  var pendingT = null;
  window.STORYBOARD_ASSETS = window.STORYBOARD_ASSETS || {};

  function post(message) {
    if (window.parent && window.parent !== window) window.parent.postMessage(message, "*");
  }
  function describe(error) {
    if (error && error.message) return String(error.message);
    return typeof error === "string" ? error : "neznámá chyba";
  }
  function quote(id) { return window.CSS && CSS.escape ? CSS.escape(id) : String(id).replace(/[^a-z0-9-]/gi, ""); }
  // Schované vrstvy: visibility, aby se rozvržení scény neměnilo.
  function applyHidden() {
    if (!hiddenStyle) {
      hiddenStyle = document.createElement("style");
      hiddenStyle.setAttribute("data-storyboard", "hidden-layers");
      (document.head || document.documentElement).appendChild(hiddenStyle);
    }
    hiddenStyle.textContent = hidden.map(function (id) { return '[data-layer="' + quote(id) + '"]{visibility:hidden !important}'; }).join("\n");
  }
  // CSS animace a přechody: čas od nejbližšího předka s data-t0 (bez něj 0), pozastavené, takže stejný t = stejný snímek.
  function alignAnimations(t) {
    var list = document.getAnimations ? document.getAnimations() : [];
    list.forEach(function (anim) {
      var target = anim.effect && anim.effect.target;
      var holder = target && target.closest ? target.closest("[data-t0]") : null;
      var t0 = holder ? parseFloat(holder.getAttribute("data-t0")) || 0 : 0;
      anim.pause();
      anim.currentTime = Math.max(0, (t - t0) * 1000);
    });
  }

  window.seek = function (t) {
    var state = stateAt(window.STORYBOARD_DATA, t);
    var root = document.documentElement;
    Object.keys(state).forEach(function (key) {
      var v = state[key];
      root.style.setProperty("--" + key, typeof v === "boolean" ? (v ? "1" : "0") : String(v));
    });
    if (!window.scene || typeof window.scene.seek !== "function") throw new Error(NO_SEEK);
    window.scene.seek(t, state);
    alignAnimations(t);
    applyHidden();
  };

  function safeSeek(t) {
    try { window.seek(t); } catch (error) { post({ type: "error", message: describe(error) }); }
  }
  function markReady() {
    if (ready) return true;
    if (!window.scene || typeof window.scene.seek !== "function") return false;
    ready = true;
    window.STORYBOARD_READY = true;
    post({ type: "ready" });
    if (pendingT !== null) safeSeek(pendingT);
    else if (window.STORYBOARD_DATA) safeSeek(0);
    return true;
  }
  document.addEventListener("DOMContentLoaded", markReady);
  window.addEventListener("load", function () { if (!markReady()) post({ type: "error", message: NO_SEEK }); });
  window.addEventListener("error", function (event) { post({ type: "error", message: describe(event.error || event.message) }); });

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) return;
    var data = event.data || {};
    if (data.type === "board") {
      window.STORYBOARD_DATA = data.board;
      window.STORYBOARD_ASSETS = data.assets || {};
      hidden = Array.isArray(data.hidden) ? data.hidden : [];
      applyHidden();
    } else if (data.type === "seek") {
      pendingT = Number(data.t) || 0;
      if (ready) safeSeek(pendingT);
    }
  });
})();
