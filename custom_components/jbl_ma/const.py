"""Constants and per-model feature tables for the JBL MA series integration."""
from __future__ import annotations

DOMAIN = "jbl_ma"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_MODEL = "model"

DEFAULT_PORT = 50000

# Model id (from cmd 0x50 init response) -> human name.
MODELS: dict[int, str] = {
    1: "MA510",
    2: "MA710",
    3: "MA7100HP",
    4: "MA9100HP",
}

# Source id <-> name. The AVR reports the id; we present the name to HA.
SOURCES: dict[int, str] = {
    0x01: "TV (ARC)",
    0x02: "HDMI 1",
    0x03: "HDMI 2",
    0x04: "HDMI 3",
    0x05: "HDMI 4",
    0x06: "HDMI 5",
    0x07: "HDMI 6",
    0x08: "Coax",
    0x09: "Optical",
    0x0A: "Analog 1",
    0x0B: "Analog 2",
    0x0C: "Phono",
    0x0D: "Bluetooth",
    0x0E: "Network",
}

SURROUND_MODES: dict[int, str] = {
    0x01: "Dolby Surround",
    0x02: "DTS Neural:X",
    0x03: "Stereo 2.0",
    0x04: "Stereo 2.1",
    0x05: "All Stereo",
    0x06: "Native",
    0x07: "Dolby ProLogic II",
}

DIM_LEVELS: dict[int, str] = {
    0x00: "Full",
    0x01: "50%",
    0x02: "25%",
    0x03: "Off",
}

DOLBY_MODES: dict[int, str] = {
    0x00: "Off",
    0x01: "Music",
    0x02: "Movie",
    0x03: "Night",
}

ROOM_EQ_MODES: dict[int, str] = {
    0x00: "Disabled",
    0x01: "EZ Set EQ",
    0x02: "Dirac Live",
}

STREAM_SERVERS: dict[int, str] = {
    0: "None",
    1: "Airable",
    4: "USB Storage",
    6: "VTuner",
    9: "TuneIn",
    10: "UPnP",
    11: "QPlay",
    12: "Bluetooth",
    13: "AirPlay",
    15: "Spotify",
    16: "Google Cast",
    17: "Airable Radios",
    18: "Airable Podcasts",
    19: "Napster",
    20: "Qobuz",
    21: "Deezer",
    22: "Tidal",
    23: "Roon",
    26: "Amazon Music",
    33: "Pandora",
}

STREAM_STATES: dict[int, str] = {
    0: "Stopped",
    1: "Playing",
    2: "Paused",
}

# IR codes for the simulate-IR command (0x04). 24-bit NEC.
IR_CODES: dict[str, int] = {
    "power": 0x010E03,
    "up": 0x010E99,
    "down": 0x010E59,
    "left": 0x010E83,
    "right": 0x010E43,
    "ok": 0x010E21,
    "menu": 0x010ECA,
    "back": 0x010EA1,
    "dim": 0x010EC9,
    "vol_up": 0x010EE3,
    "vol_down": 0x010E13,
    "source_next": 0x010E8C,
    "source_prev": 0x010E0C,
    "surr_up": 0x010EF4,
    "surr_down": 0x010E74,
    "mute": 0x010EC3,
    "main_zone_power_on": 0x010ED9,
    "main_zone_power_off": 0x010EF9,
    "zone2_party_on": 0x010E73,
    "zone2_party_off": 0x010E8B,
    "zone2_party_vol_up": 0x010E39,
    "zone2_party_vol_down": 0x010EB9,
    "main_zone_tv": 0x010E71,
    "main_zone_hdmi1": 0x010E11,
    "main_zone_hdmi2": 0x010E91,
    "main_zone_hdmi3": 0x010E51,
    "main_zone_hdmi4": 0x010ED1,
    "main_zone_hdmi5": 0x010E31,
    "main_zone_hdmi6": 0x010EB1,
    "main_zone_coax": 0x010E81,
    "main_zone_optical": 0x010EDB,
    "main_zone_analog1": 0x010E23,
    "main_zone_analog2": 0x010E33,
    "main_zone_phono": 0x010E0B,
    "main_zone_bluetooth": 0x010E53,
    "main_zone_network": 0x010ED3,
}

# Per-model feature gates. True == feature is supported on that model.
# Order tracks the docs: MA710/MA7100HP/MA9100HP support most extras; MA510 is
# the entry-level model with ProLogic II instead of Dolby Surround/DTS Neural:X.
MODEL_FEATURES: dict[int, dict[str, bool]] = {
    1: {  # MA510
        "hdmi5_6": False,
        "phono": False,
        "party": False,
        "drc": False,
        "dolby_night": False,
        "dolby_surround": False,
        "dts_neuralx": False,
        "prologic2": True,
        "dirac": False,
    },
    2: {  # MA710
        "hdmi5_6": True,
        "phono": True,
        "party": True,
        "drc": True,
        "dolby_night": True,
        "dolby_surround": True,
        "dts_neuralx": True,
        "prologic2": False,
        "dirac": False,
    },
    3: {  # MA7100HP
        "hdmi5_6": True,
        "phono": True,
        "party": True,
        "drc": True,
        "dolby_night": True,
        "dolby_surround": True,
        "dts_neuralx": True,
        "prologic2": False,
        "dirac": True,
    },
    4: {  # MA9100HP
        "hdmi5_6": True,
        "phono": True,
        "party": True,
        "drc": True,
        "dolby_night": True,
        "dolby_surround": True,
        "dts_neuralx": True,
        "prologic2": False,
        "dirac": True,
    },
}


def feature(model: int | None, name: str) -> bool:
    """Return True if `model` supports feature `name`. Unknown model -> True."""
    if model is None:
        return True
    return MODEL_FEATURES.get(model, {}).get(name, True)


def supported_sources(model: int | None) -> dict[int, str]:
    out = dict(SOURCES)
    if not feature(model, "hdmi5_6"):
        out.pop(0x06, None)
        out.pop(0x07, None)
    if not feature(model, "phono"):
        out.pop(0x0C, None)
    return out


def supported_surround(model: int | None) -> dict[int, str]:
    out = dict(SURROUND_MODES)
    if not feature(model, "dolby_surround"):
        out.pop(0x01, None)
    if not feature(model, "dts_neuralx"):
        out.pop(0x02, None)
    if not feature(model, "prologic2"):
        out.pop(0x07, None)
    return out


def supported_dolby(model: int | None) -> dict[int, str]:
    out = dict(DOLBY_MODES)
    if not feature(model, "dolby_night"):
        out.pop(0x03, None)
    return out


def supported_room_eq(model: int | None) -> dict[int, str]:
    out = dict(ROOM_EQ_MODES)
    if not feature(model, "dirac"):
        out.pop(0x02, None)
    return out
