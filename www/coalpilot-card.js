/**
 * CoalPilot Card — Lovelace card for the CoalPilot integration.
 * Ember-themed shisha oven timer that learns your perfect burn time.
 * Dependency-free custom element (no build step required).
 */

const FONT_LINK_ID = "coalpilot-fonts";
const ACCENT_DEFAULT = "#ff5722";

function ensureFonts() {
  if (document.getElementById(FONT_LINK_ID)) return;
  const link = document.createElement("link");
  link.id = FONT_LINK_ID;
  link.rel = "stylesheet";
  link.href =
    "https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap";
  document.head.appendChild(link);
}

const fmt = (s) => {
  s = Math.max(0, Math.round(Number(s) || 0));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

const VERDICT_LABEL = { perfect: "Perfekt", shorter: "Kürzer", longer: "Länger" };

class CoalPilotCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    // local pre-start selections (idle only)
    this._sel = { mode: null, coal: null, count: null, fixed: null };
    this._rendered = false;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("coalpilot-card: 'entity' (the CoalPilot state sensor) is required");
    }
    this._config = config;
    ensureFonts();
  }

  getCardSize() {
    return 8;
  }

  static getStubConfig(hass) {
    const ent = Object.keys(hass?.states || {}).find(
      (e) => e.startsWith("sensor.") && hass.states[e].attributes?.coal_types
    );
    return { entity: ent || "sensor.shisha_ofen_state" };
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  // ---- helpers ----------------------------------------------------------

  get _state() {
    return this._hass?.states?.[this._config.entity];
  }

  get _attrs() {
    return this._state?.attributes || {};
  }

  get _accent() {
    return this._config.accent_color || ACCENT_DEFAULT;
  }

  _remaining() {
    // prefer the dedicated remaining sensor for 1s resolution
    const base = this._config.entity.replace(/_state$/, "_remaining");
    const rs = this._hass?.states?.[base];
    if (rs && !isNaN(Number(rs.state))) return Number(rs.state);
    return Number(this._attrs.remaining || 0);
  }

  _selectedCoal() {
    const a = this._attrs;
    if (a.phase === "idle" && this._sel.coal) return this._sel.coal;
    return a.selected_coal;
  }

  _coalObj(id) {
    return (this._attrs.coal_types || []).find((c) => c.id === id);
  }

  _mode() {
    const a = this._attrs;
    if (a.phase === "idle" && this._sel.mode) return this._sel.mode;
    return a.mode || "auto";
  }

  _baseTime() {
    const a = this._attrs;
    if (this._mode() === "fixed") {
      return this._sel.fixed != null ? this._sel.fixed : a.fixed_time || 0;
    }
    const coal = this._coalObj(this._selectedCoal());
    return coal ? coal.learned_time : a.learned || 0;
  }

  _call(service, data) {
    const entryId = this._attrs.entry_id; // not always present; fall back to none
    const payload = { ...data };
    return this._hass.callService("coalpilot", service, payload, {
      entity_id: this._config.entity,
    });
  }

  // ---- actions ----------------------------------------------------------

  _start() {
    const mode = this._mode();
    const data = { mode };
    if (mode === "fixed") {
      data.fixed_time = this._baseTime();
    } else {
      const coal = this._selectedCoal();
      if (coal) data.coal_type = coal;
      const count = this._sel.count ?? this._coalObj(coal)?.default_count;
      if (count) data.count = count;
    }
    this._call("start", data);
  }

  _finish() {
    this._call("finish", {});
  }

  _feedback(verdict) {
    this._call("feedback", { verdict });
  }

  _stepFixed(delta) {
    const cur = this._baseTime();
    this._sel.fixed = Math.max(60, cur + delta);
    this._call("set_fixed_time", { fixed_time: this._sel.fixed });
    this._update();
  }

  // ---- render -----------------------------------------------------------

  _update() {
    if (!this._hass || !this._config) return;
    if (!this._state) {
      this.shadowRoot.innerHTML = `<div style="padding:16px;color:var(--error-color,#c00)">CoalPilot: Entity <code>${this._config.entity}</code> nicht gefunden.</div>`;
      return;
    }
    if (!this._rendered) this._buildSkeleton();
    this._paint();
  }

  _buildSkeleton() {
    const a = this._accent;
    this.shadowRoot.innerHTML = `
      <style>
        @keyframes floatUp {0%{transform:translateY(6px);opacity:0}100%{transform:translateY(0);opacity:1}}
        :host{--cp-accent:${a};}
        .wrap{display:block;font-family:'Inter Tight',system-ui,sans-serif;color:#e7e9ec;
          background:linear-gradient(180deg,#15181d,#101318);border:1px solid #23272e;
          border-radius:var(--ha-card-border-radius,28px);padding:26px 24px 22px;
          box-shadow:0 30px 80px -30px rgba(0,0,0,.8),inset 0 1px 0 rgba(255,255,255,.04);box-sizing:border-box}
        .hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
        .hl{display:flex;align-items:center;gap:11px}
        .tile{width:38px;height:38px;border-radius:12px;display:flex;align-items:center;justify-content:center;
          background:linear-gradient(135deg,#ff8a3d,var(--cp-accent));box-shadow:0 6px 18px -4px rgba(255,87,34,.6)}
        .title{font-size:16px;font-weight:700;letter-spacing:-.01em}
        .sub{font-size:11.5px;color:#7c8290;font-weight:500}
        .pill{display:flex;align-items:center;gap:7px;padding:5px 11px;border-radius:999px;border:1px solid #23272e}
        .dot{width:7px;height:7px;border-radius:999px}
        .pilltxt{font-size:11px;font-weight:600}
        .seg{display:flex;gap:4px;padding:4px;background:#0c0e12;border:1px solid #23272e;border-radius:14px;margin-bottom:22px}
        .seg button{padding:9px 0;flex:1;border-radius:11px;border:none;cursor:pointer;font-size:13px;font-weight:600;
          font-family:inherit;background:transparent;color:#7c8290;transition:all .2s}
        .seg button.on{background:linear-gradient(135deg,#ff8a3d,var(--cp-accent));color:#fff;box-shadow:0 4px 14px -4px rgba(255,87,34,.6)}
        .dial{position:relative;width:236px;height:236px;margin:0 auto 18px}
        .dial .clock{font-family:'DM Mono',monospace;font-size:46px;font-weight:500;letter-spacing:-.02em;line-height:1;color:#fff;font-variant-numeric:tabular-nums}
        .dial .dsub{font-size:11.5px;color:#7c8290;margin-top:8px;font-weight:500;text-transform:uppercase;letter-spacing:.08em}
        .center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
        .prog{transition:stroke-dashoffset .6s linear}
        .row{display:flex;align-items:center;justify-content:center;gap:16px;margin-bottom:18px}
        .step{width:44px;height:44px;border-radius:14px;background:#0c0e12;border:1px solid #23272e;color:#e7e9ec;font-size:22px;cursor:pointer;font-weight:600}
        .steplbl{font-family:'DM Mono',monospace;font-size:15px;color:#a7adb8;min-width:78px;text-align:center}
        .primary{width:100%;padding:16px;border-radius:16px;border:none;cursor:pointer;font-size:15px;font-weight:700;font-family:inherit;letter-spacing:-.01em;transition:transform .12s}
        .primary.go{background:linear-gradient(135deg,#ff8a3d,var(--cp-accent));color:#fff;box-shadow:0 10px 30px -8px rgba(255,87,34,.6)}
        .primary.stop{background:#0c0e12;color:#e7e9ec;border:1px solid #23272e}
        .fb{animation:floatUp .35s ease}
        .fbh{text-align:center;font-size:14.5px;font-weight:600;margin-bottom:4px}
        .fbs{text-align:center;font-size:12px;color:#7c8290;margin-bottom:14px}
        .fbg{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
        .fbb{display:flex;flex-direction:column;align-items:center;gap:3px;padding:12px 4px;border-radius:14px;background:#0c0e12;border:1px solid #23272e;color:#e7e9ec;cursor:pointer;font-family:inherit}
        .fbb.perf{background:rgba(255,87,34,.12);border:1px solid rgba(255,87,34,.4);color:#fff}
        .lbl{font-size:11px;color:#7c8290;font-weight:600;text-transform:uppercase;letter-spacing:.06em}
        .coalsel{margin-top:14px}
        select,.cnt{width:100%;box-sizing:border-box;background:#0c0e12;border:1px solid #23272e;border-radius:12px;padding:11px 13px;color:#e7e9ec;font-size:13px;font-family:inherit;outline:none}
        .cntrow{display:flex;gap:10px;margin-top:10px;align-items:center}
        .cntrow .step{width:38px;height:38px;font-size:18px;border-radius:12px}
        .cntval{flex:1;text-align:center;font-family:'DM Mono',monospace;font-size:14px;color:#a7adb8}
        .stats{display:flex;gap:10px;margin-top:18px}
        .stat{flex:1;background:#0c0e12;border:1px solid #23272e;border-radius:14px;padding:12px 13px}
        .stat .v1{font-family:'DM Mono',monospace;font-size:17px;color:#ff9d5c}
        .stat .v2{font-size:13px;color:#c7ccd4;font-weight:500;line-height:1.35}
        .hist{margin-top:16px}
        .hrow{display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid #1a1e24}
        .htime{font-family:'DM Mono',monospace;font-size:13px;color:#e7e9ec;min-width:46px}
        .hcoal{font-size:12px;color:#7c8290;flex:1}
        .hverd{font-size:11px;font-weight:600}
        .mt5{margin-bottom:5px}
      </style>
      <ha-card class="wrap">
        <div class="hdr">
          <div class="hl">
            <div class="tile"><svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 3c1.5 3-1.5 4 0 6.5C13.8 8 15 6.5 14.5 4c2.5 1.8 4 4.6 4 7.5a6.5 6.5 0 1 1-13 0c0-1.6.6-3 1.6-4C7 9 8.4 9.6 9 11c.6-3 1-5 3-8Z" fill="#fff"/></svg></div>
            <div><div class="title" id="cp-title">Shisha Ofen</div><div class="sub" id="cp-status"></div></div>
          </div>
          <div class="pill" id="cp-pill"><span class="dot" id="cp-dot"></span><span class="pilltxt" id="cp-plabel"></span></div>
        </div>
        <div class="seg" id="cp-seg">
          <button data-mode="auto">Auto-Lernen</button>
          <button data-mode="fixed">Feste Zeit</button>
        </div>
        <div class="dial">
          <svg width="236" height="236" viewBox="0 0 236 236" style="transform:rotate(-90deg)">
            <circle cx="118" cy="118" r="104" fill="none" stroke="#1c2026" stroke-width="14"/>
            <circle id="cp-prog" class="prog" cx="118" cy="118" r="104" fill="none" stroke="url(#cpGrad)" stroke-width="14" stroke-linecap="round"/>
            <defs><linearGradient id="cpGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffb648"/><stop offset="1" stop-color="#ff4d1a"/></linearGradient></defs>
          </svg>
          <div class="center"><div class="clock" id="cp-clock">00:00</div><div class="dsub" id="cp-dsub"></div></div>
        </div>
        <div class="row" id="cp-stepper" style="display:none">
          <button class="step" id="cp-dec">−</button>
          <div class="steplbl">feste Zeit</div>
          <button class="step" id="cp-inc">+</button>
        </div>
        <button class="primary" id="cp-primary"></button>
        <div class="fb" id="cp-fb" style="display:none">
          <div class="fbh">Wie war die Kohle?</div>
          <div class="fbs">Passt die Zeit fürs nächste Mal an</div>
          <div class="fbg">
            <button class="fbb" data-v="shorter"><span style="font-size:19px">🥶</span><span style="font-size:11.5px;font-weight:600">Kürzer</span><span style="font-size:10px;color:#7c8290">−30s</span></button>
            <button class="fbb perf" data-v="perfect"><span style="font-size:19px">🔥</span><span style="font-size:11.5px;font-weight:600">Perfekt</span><span style="font-size:10px;color:#ff9d5c">gemerkt</span></button>
            <button class="fbb" data-v="longer"><span style="font-size:19px">🥵</span><span style="font-size:11.5px;font-weight:600">Länger</span><span style="font-size:10px;color:#7c8290">+30s</span></button>
          </div>
        </div>
        <div class="coalsel" id="cp-coalsel">
          <div class="lbl mt5" style="margin-bottom:7px">Kohle</div>
          <select id="cp-coal"></select>
          <div class="cntrow"><button class="step" id="cp-cdec">−</button><div class="cntval" id="cp-cval"></div><button class="step" id="cp-cinc">+</button></div>
        </div>
        <div class="stats">
          <div class="stat"><div class="lbl mt5">Gelernte Zeit</div><div class="v1" id="cp-learned">--:--</div></div>
          <div class="stat"><div class="lbl mt5">Letzte Session</div><div class="v2" id="cp-last">—</div></div>
        </div>
        <div class="hist" id="cp-hist" style="display:none">
          <div class="lbl" style="margin-bottom:9px">Verlauf</div>
          <div id="cp-histlist"></div>
        </div>
      </ha-card>`;

    const $ = (id) => this.shadowRoot.getElementById(id);
    $("cp-seg").querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        if (this._attrs.phase !== "idle") return;
        this._sel.mode = b.dataset.mode;
        this._paint();
      })
    );
    $("cp-primary").addEventListener("click", () =>
      this._attrs.phase === "running" ? this._finish() : this._start()
    );
    $("cp-dec").addEventListener("click", () => this._stepFixed(-30));
    $("cp-inc").addEventListener("click", () => this._stepFixed(30));
    $("cp-fb").querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => this._feedback(b.dataset.v))
    );
    $("cp-coal").addEventListener("change", (e) => {
      this._sel.coal = e.target.value;
      this._sel.count = null;
      this._paint();
    });
    $("cp-cdec").addEventListener("click", () => {
      const c = this._curCount();
      this._sel.count = Math.max(1, c - 1);
      this._paint();
    });
    $("cp-cinc").addEventListener("click", () => {
      const c = this._curCount();
      this._sel.count = Math.min(10, c + 1);
      this._paint();
    });
    this._rendered = true;
  }

  _curCount() {
    if (this._sel.count != null) return this._sel.count;
    const coal = this._coalObj(this._selectedCoal());
    return coal?.default_count || 1;
  }

  _paint() {
    const $ = (id) => this.shadowRoot.getElementById(id);
    const a = this._attrs;
    const phase = a.phase || "idle";
    const idle = phase === "idle",
      running = phase === "running",
      fb = phase === "feedback";
    const mode = this._mode();

    // reset local selections when leaving idle so backend wins
    if (!idle) this._sel = { mode: null, coal: null, count: null, fixed: null };

    $("cp-title").textContent = this._config.title || this._hass.states[this._config.entity]?.attributes?.friendly_name?.replace(/ State$/, "") || "Shisha Ofen";
    $("cp-status").textContent = mode === "fixed" ? "Feste-Zeit-Modus" : "Lernt deine perfekte Zeit";

    // pill
    const pill = $("cp-pill"), dot = $("cp-dot"), pl = $("cp-plabel");
    if (running) {
      pill.style.background = "rgba(255,87,34,.14)"; pill.style.borderColor = "rgba(255,87,34,.35)";
      dot.style.background = "#ff5722"; dot.style.boxShadow = "0 0 8px #ff5722";
      pl.style.color = "#ff9d5c"; pl.textContent = "Läuft";
    } else if (fb) {
      pill.style.background = "rgba(255,157,92,.14)"; pill.style.borderColor = "rgba(255,157,92,.35)";
      dot.style.background = "#ff9d5c"; dot.style.boxShadow = "0 0 8px #ff9d5c";
      pl.style.color = "#ff9d5c"; pl.textContent = "Fertig";
    } else {
      pill.style.background = "rgba(124,130,144,.12)"; pill.style.borderColor = "#23272e";
      dot.style.background = "#7c8290"; dot.style.boxShadow = "0 0 8px #7c8290";
      pl.style.color = "#a7adb8"; pl.textContent = "Bereit";
    }

    // segmented control
    $("cp-seg").querySelectorAll("button").forEach((b) => {
      b.classList.toggle("on", b.dataset.mode === mode);
      b.style.pointerEvents = idle ? "auto" : "none";
    });

    // dial
    const total = running ? Number(a.total || 0) : this._baseTime();
    const remaining = running ? this._remaining() : fb ? 0 : this._baseTime();
    const R = 104, C = 2 * Math.PI * R;
    const prog = total > 0 ? remaining / total : 0;
    const off = running ? C * (1 - prog) : fb ? C : 0;
    const p = $("cp-prog");
    p.setAttribute("stroke-dasharray", `${C} ${C}`);
    p.setAttribute("stroke-dashoffset", off);
    $("cp-clock").textContent = fmt(remaining);
    $("cp-dsub").textContent = running ? "verbleibend" : fb ? "abgelaufen" : mode === "fixed" ? "feste Laufzeit" : "geplant";

    // stepper (fixed + idle)
    $("cp-stepper").style.display = idle && mode === "fixed" ? "flex" : "none";

    // primary
    const prim = $("cp-primary");
    prim.style.display = idle || running ? "block" : "none";
    if (running) {
      prim.className = "primary stop"; prim.textContent = "Jetzt beenden";
    } else {
      prim.className = "primary go"; prim.textContent = "▶  Ofen starten";
    }

    // feedback
    $("cp-fb").style.display = fb ? "block" : "none";

    // coal selector (idle + auto)
    const showCoal = idle && mode === "auto";
    $("cp-coalsel").style.display = showCoal ? "block" : "none";
    if (showCoal) {
      const sel = $("cp-coal");
      const coals = a.coal_types || [];
      const cur = this._selectedCoal();
      if (sel.dataset.sig !== JSON.stringify(coals.map((c) => [c.id, c.name, c.size_mm]))) {
        sel.innerHTML = coals.length
          ? coals.map((c) => `<option value="${c.id}">${c.name} · ${c.size_mm}mm${c.is_default ? " ★" : ""}</option>`).join("")
          : `<option value="">Keine Kohlearten – erst anlegen</option>`;
        sel.dataset.sig = JSON.stringify(coals.map((c) => [c.id, c.name, c.size_mm]));
      }
      if (cur) sel.value = cur;
      $("cp-cval").textContent = `${this._curCount()} Stück`;
    }

    // stats
    $("cp-learned").textContent = fmt(this._coalObj(this._selectedCoal())?.learned_time ?? a.learned ?? 0);
    $("cp-last").textContent = a.last_session || "—";

    // history
    const hist = a.history || [];
    $("cp-hist").style.display = hist.length ? "block" : "none";
    if (hist.length) {
      $("cp-histlist").innerHTML = hist
        .map(
          (h) => `<div class="hrow"><span style="font-size:15px">${h.icon}</span>
            <span class="htime">${h.time}</span><span class="hcoal">${h.coal}</span>
            <span class="hverd" style="color:${h.verdict === "perfect" ? "#ff9d5c" : "#7c8290"}">${VERDICT_LABEL[h.verdict] || ""}</span></div>`
        )
        .join("");
    }
  }
}

customElements.define("coalpilot-card", CoalPilotCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "coalpilot-card",
  name: "CoalPilot Card",
  description: "Shisha oven timer that learns your perfect burn time.",
  preview: true,
});
console.info("%c COALPILOT-CARD %c v0.1.0 ", "background:#ff5722;color:#fff;border-radius:4px 0 0 4px;padding:2px 6px", "background:#0c0e12;color:#ff9d5c;border-radius:0 4px 4px 0;padding:2px 6px");
