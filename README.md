# JBL MA Series AVR — Home Assistant integration

Control JBL MA510 / MA710 / MA7100HP / MA9100HP AV receivers from Home
Assistant over the AVR's built-in TCP IP-control protocol (port 50000).

The integration speaks the protocol natively — no cloud, no extra hardware,
no IR blaster. State changes you make on the front panel or with the
physical remote are pushed to HA in real time.

Implements the protocol from `IPControl_MA_Series_v17.pdf` (rev 1.7,
Nov 2024).

## Features

- **Media player** entity: power, volume, mute, source select, sound mode
  (Dolby Surround / DTS Neural:X / Stereo / All Stereo / Native / ProLogic II)
- **Numbers**: treble (-12…+12 dB), bass (-12…+12 dB), party-out volume
- **Selects**: input source, surround mode, display dim, Dolby Audio mode
  (Off / Music / Movie / Night), Room EQ (EZ Set / Dirac Live)
- **Switches**: party mode, dialog enhancement, Dolby/DTS DRC
- **Buttons**:
  - virtual remote — Up / Down / Left / Right / OK / Back / Menu / Dim
  - admin — reboot, factory reset (disabled by default)
- **Web UI link**: the AVR's built-in web interface (`https://<host>/webclient/`)
  is exposed via `configuration_url` on the device — open it in one click
  from the device card's "Visit" link in the top-right.
- **Sensors**: streaming source name + play state
- **Services**: `jbl_ma.send_ir` (named or raw NEC code),
  `jbl_ma.send_raw` (arbitrary command + data bytes)

Per-model feature gating is built in — an MA510 won't show a Phono source,
HDMI 5/6, party mode, DRC, or Dirac Live.

## Requirements

- Home Assistant 2024.6 or later
- The AVR must be on the same LAN and **not** in Green standby mode (IP
  control is disabled in that state per the JBL spec).

## Installation

### HACS (custom repository)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kernelorg&repository=hacs-jbl-premium-audio&category=integration)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add this repository, category **Integration**
3. Install **JBL MA Series AVR**, restart Home Assistant
4. Settings → Devices & Services → **Add Integration** → "JBL MA Series AVR"

### Manual

Copy `custom_components/jbl_ma/` into your Home Assistant
`config/custom_components/` directory and restart HA.

## Configuration

The AVR is discovered automatically over **mDNS / Zeroconf** on the LAN —
when Home Assistant sees a JBL MA receiver, it appears under
**Settings → Devices & Services** as a discovered device that you only need
to confirm.

> **Restart Home Assistant after installing or updating the integration.**
> The mDNS service-type subscriptions in `manifest.json` are read at HA
> startup. Reloading the integration (or just installing via HACS without a
> restart) won't be enough — you need a full HA restart for the zeroconf
> browser to start listening for JBL records. Discovery should then appear
> within ~30 s.
>
> If your HA host and the AVR are on different VLANs / subnets, multicast
> traffic typically doesn't traverse the boundary — discovery won't work
> there and you should fall back to manual host entry.

Manual entry remains available as a fallback: choose **Add Integration → JBL
MA Series AVR** and type the IP. Either path probes the AVR with the init
command (`0x50`), reads the model byte, and uses it to decide which features
to expose.

### What the integration listens for

The AVR advertises several services; the integration matches on the most
reliable property markers:

| Service               | Match (manifest matcher)                                |
| --------------------- | ------------------------------------------------------- |
| `_airplay._tcp.`      | `properties.model = JBL MA*` or `manufacturer = Harman Luxury Audio*` |
| `_raop._tcp.`         | `properties.am = JBL MA*`                               |
| `_googlecast._tcp.`   | `name = jbl-ma*` or `properties.md = JBL MA*`           |
| `_tidalconnect._tcp.` | `name = jbl ma*` or `properties.mn = JBL MA*`           |
| `_sues800device._tcp.`| `properties.manufacturer = Harman Luxury Audio*` (Harman-specific) |

## One-click web-UI shortcut on a dashboard

The standard "Visit" link on the device card is one click. If you want the
same affordance on a Lovelace dashboard, add a Button card with a URL
`tap_action`:

```yaml
type: button
name: JBL Web UI
icon: mdi:web
tap_action:
  action: url
  url_path: https://192.168.89.6/webclient/
  new_tab: true
```

Home Assistant button entities can't trigger browser navigation from the
server side, which is why this is exposed as a Lovelace tap_action instead
of an entity.

## Services

### `jbl_ma.send_ir`

Simulate a remote-control button press.

```yaml
service: jbl_ma.send_ir
data:
  device_id: <pick the AVR device>
  code: main_zone_hdmi1   # or 0x010E11
```

Named codes: `power`, `up`, `down`, `left`, `right`, `ok`, `menu`, `back`,
`dim`, `vol_up`, `vol_down`, `source_next`, `source_prev`, `surr_up`,
`surr_down`, `mute`, `main_zone_power_on`, `main_zone_power_off`,
`zone2_party_on`, `zone2_party_off`, `zone2_party_vol_up`,
`zone2_party_vol_down`, `main_zone_tv`, `main_zone_hdmi1`–`main_zone_hdmi6`,
`main_zone_coax`, `main_zone_optical`, `main_zone_analog1`,
`main_zone_analog2`, `main_zone_phono`, `main_zone_bluetooth`,
`main_zone_network`.

### `jbl_ma.send_raw`

Escape hatch for raw commands (for protocol experimentation or commands not
yet exposed as entities).

```yaml
service: jbl_ma.send_raw
data:
  device_id: <pick the AVR device>
  command_id: 0x06   # master volume
  data: [0x28]       # 40
```

## Notes / known limitations

- The AVR enforces per-model feature support. If you send a command the
  current model doesn't support, the AVR replies with `0xC1`/`0xC3` and the
  client logs a debug warning — the entity simply stays at its prior value.
- Volume is mapped 0–99 ⇄ 0.0–1.0 with rounding, so the UI may show small
  step rounding (e.g. 0.51 instead of 0.5).
- Heartbeat is sent every 30 s; on failure, the client closes and reconnects
  with exponential backoff (1 s → 60 s).
