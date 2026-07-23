# 🔥 CoalPilot

**Smart shisha / hookah coal timer for Home Assistant — it learns your perfect burn time.**
*Der smarte Shisha-Kohle-Timer für Home Assistant, der deine perfekte Zeit selbst lernt.*

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![release](https://img.shields.io/github/v/release/bonderaustria/ha-coalpilot?color=ff5722&label=release)](https://github.com/bonderaustria/ha-coalpilot/releases)

CoalPilot switches your oven (any `switch`, `input_boolean` or `light`) on, runs a burn timer, and after every session you tap **Shorter / Perfect / Longer**. It learns the ideal time **per coal type** (26 mm burns longer than 20 mm), tracks statistics you can graph, and can push a notification the moment the coal is ready.

<p align="center">
  <img src="https://raw.githubusercontent.com/bonderaustria/ha-coalpilot/master/docs/images/idle.png" width="30%" alt="Ready" />
  <img src="https://raw.githubusercontent.com/bonderaustria/ha-coalpilot/master/docs/images/running.png" width="30%" alt="Running" />
  <img src="https://raw.githubusercontent.com/bonderaustria/ha-coalpilot/master/docs/images/feedback.png" width="30%" alt="Feedback" />
</p>

---

## ✨ Features

- 🎯 **Self-learning timer** — separate, smoothed learned time for every coal type
- 🥄 **Coal library** — define your coals once (name, size, shape, default count), then pick one from a dropdown at start; mark one as default
- ⏱️ **Auto or fixed mode** — let it learn, or set a fixed time with ±30 s steps
- 📊 **Statistics entities** — sessions today / week / month / year / total via Home Assistant's own long-term stats, plus per-coal counts, total oven runtime and average burn time
- 🔔 **Optional notification** — title + message with placeholders `{kohle}`, `{dauer}`, `{ofen}`, `{uhrzeit}` sent when the timer finishes
- 🎨 **Beautiful "Ember" Lovelace card** — dark, glowing, mobile-friendly
- 🌍 **English & German** UI and docs
- 🏠 **Multiple ovens** supported (add the integration more than once)

---

## 📦 Installation

### 1. Integration (via HACS — recommended)

1. HACS → **Integrations** → three-dot menu → **Custom repositories**.
2. Add `https://github.com/bonderaustria/ha-coalpilot` as category **Integration**.
3. Install **CoalPilot**, then **restart Home Assistant**.

<details><summary>Manual installation</summary>

Copy `custom_components/coalpilot` into your Home Assistant `config/custom_components/` folder and restart.
</details>

### 2. Lovelace card — nothing to install

The card ships **inside the integration** and is registered on the frontend automatically. You don't copy any file and you don't add a dashboard resource. After installing the integration and restarting, the `custom:coalpilot-card` is ready to use.

> If the card doesn't appear right after the update, hard-refresh your browser once (Ctrl/Cmd+Shift+R) to clear the cached frontend.

---

## ⚙️ Setup

1. **Settings → Devices & Services → Add Integration → CoalPilot.**
2. Choose a **name**, your **oven switch**, and a default burn time.
3. Open **Configure** on the new entry to:
   - **Add coal types** (name, size in mm, shape, default count, starting time, default flag)
   - Set up an optional **notification** (service + title + message)
   - Tweak settings (default time, feedback-on-early-stop)

### Add the card

```yaml
type: custom:coalpilot-card
entity: sensor.shisha_ofen_state   # the CoalPilot "State" sensor
# optional:
# title: Wohnzimmer Ofen
# accent_color: "#ff5722"
```

You can also add it from the dashboard UI: **Edit dashboard → Add card → search "CoalPilot"**.

---

## 🌍 Language / Sprache (DE ⇄ EN)

CoalPilot is fully bilingual — **the config screens, the entities and the card all follow the Home Assistant user language**. There is no separate setting in the integration.

**Switch a user between German and English:**
1. Click your **profile** (bottom-left avatar in Home Assistant).
2. Under **Language**, pick **English** or **Deutsch**.
3. The card and all CoalPilot texts switch immediately (reload the page if a text lags).

The language is **per user**, so each household member sees CoalPilot in their own language. Any language other than German falls back to English.

---

## 📊 Auswertungen / Statistics

CoalPilot creates these sensors per oven:

| Sensor | Purpose |
|---|---|
| `sensor.<name>_state` | Live phase + full snapshot (used by the card) |
| `sensor.<name>_remaining` | Remaining seconds |
| `sensor.<name>_learned_time` | Learned time for the selected coal |
| `sensor.<name>_sessions_total` | Total sessions (`total_increasing`) + per-coal counts |
| `sensor.<name>_oven_runtime_total` | Total burn time in hours |
| `sensor.<name>_average_burn_time` | Average burn time |

Because `sessions_total` is a `total_increasing` sensor, Home Assistant's **Statistics** and the **Statistics graph** card give you **per day / week / month / year** out of the box.

---

## 🔧 Services

`coalpilot.start`, `coalpilot.stop`, `coalpilot.finish`, `coalpilot.feedback`, `coalpilot.set_fixed_time` — all target an oven via `entry_id` (optional if you only have one). See the Developer Tools → Services UI for fields.

---

## 🧠 How the learning works

Each coal type keeps its own learned time. After a session, your verdict nudges a target (**Perfect** = the time you just burned, **Shorter/Longer** = ∓30 s), and the learned value moves toward it with a smoothing factor — so it converges without jumping around. Values stay between 1 and 30 minutes.

---

## License

[MIT](LICENSE) © Justin Tröbinger
