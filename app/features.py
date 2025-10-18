FEATURES = {
    "aussentemperatur": "heating.sensors.temperature.outside",
    "vorlauftemperatur_hk": "heating.circuits.0.temperature",
    "vorlauftemperatur_fb": "heating.circuits.1.temperature",
    "ruecklauftemperatur": "heating.sensors.temperature.return",
    "sekundaerkreis_vorlauf": "heating.secondaryCircuit.sensors.temperature.supply",
    "warmwasser_oben": "heating.dhw.sensors.temperature.dhwCylinder.top",
    "warmwasser_soll": "heating.dhw.temperature.main",
    "kompressor_anzahl_starts": ("heating.compressors.0.statistics", "starts"),
    "kompressor_laufzeit_h":    ("heating.compressors.0.statistics", "hours"),

    # Status (oft als separates Feature 'power' -> bool/an/aus)
    "kompressor_status":        "heating.compressors.0.power",
}

ALTERNATES = {
    "heating.sensors.temperature.outside": [
        "heating.sensors.temperature.outdoor"
    ],
    "heating.circuits.0.temperature": [
        "heating.circuits.0.sensors.temperature.supply",
        "heating.boiler.sensors.temperature.commonSupply"
    ],
    "heating.circuits.1.temperature": [
        "heating.circuits.1.sensors.temperature.supply"
    ],
    "heating.dhw.sensors.temperature.dhwCylinder.top": [
        "heating.bufferCylinder.sensors.temperature.top",
        "heating.buffer.sensors.temperature.top",
        "heating.dhw.sensors.temperature.hotWaterStorage.top",
    ],
    "heating.compressors.0.statistics.starts": [
        "heating.compressors.statistics.starts",
        "heating.compressor.statistics.starts",
        "heating.heatPump.compressors.0.statistics.starts",
    ],
    "heating.compressors.0.statistics.hours": [
        "heating.compressors.statistics.hours",
        "heating.compressor.statistics.hours",
        "heating.heatPump.compressors.0.statistics.hours",
        "heating.compressors.0.statistics.runtime.hours",
    ],
    "heating.compressors.0.status": [
        "heating.compressors.status",
        "heating.compressor.status",
        "heating.heatPump.compressors.0.status",
        "heating.heatPump.status.compressor",
    ],
    "heating.compressors.0.statistics": [
        "heating.heatPump.compressors.0.statistics",
        "heating.compressor.0.statistics",
        "heating.compressor.statistics",  # modellabhängig
    ],
    "heating.compressors.0.power": [
        "heating.heatPump.compressors.0.power",
        "heating.compressor.0.power",
    ],
}

def _extract_name_and_props(item):
    feat = item.get("feature")
    if isinstance(feat, dict):
        name = feat.get("name"); props = item.get("properties") or feat.get("properties") or {}
    elif isinstance(feat, str):
        name = feat; props = item.get("properties") or {}
    else:
        name = item.get("name"); props = item.get("properties") or {}
    return name, props

def _unwrap(v):
    if isinstance(v, dict):
        if "value" in v: return _unwrap(v["value"])
        for vv in v.values():
            if not isinstance(vv, (dict, list)): return vv
    return v

def _extract_value_from_props(props):
    if not isinstance(props, dict) or not props: return None
    for key in ("value","status","temperature","level","state","active"):
        if key in props: return _unwrap(props[key])
    if "value" in props and not isinstance(props["value"], dict): return props["value"]
    return None

def index_features(raw):
    by = {}
    for item in raw:
        name, props = _extract_name_and_props(item)
        if not name: continue
        by[name] = {"value": _extract_value_from_props(props), "properties": props, "raw": item}
    return by

def get_value(by_name, feature_key):
    hit = by_name.get(feature_key)
    if hit is not None: return hit["value"]
    for alt in ALTERNATES.get(feature_key, []):
        if alt in by_name: return by_name[alt]["value"]
    return None

from datetime import datetime

def extract_unit_and_timestamp(props: dict):
    """Sucht nach unit/timestamp in den Properties (falls vorhanden)."""
    if not isinstance(props, dict):
        return None, None

    # Häufigste Form: props["value"] bzw. props["status"] ist ein dict mit 'unit'/'timestamp'
    for key in ("value", "status", "temperature", "level", "state", "active"):
        pv = props.get(key)
        if isinstance(pv, dict):
            unit = pv.get("unit")
            ts = pv.get("timestamp") or pv.get("time") or pv.get("ts")
            return unit, ts
    return None, None

def normalize_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        # Viessmann liefert meist ISO-8601 -> wir normalisieren auf Sekunden
        return datetime.fromisoformat(ts.replace("Z","+00:00")).isoformat(timespec="seconds")
    except Exception:
        return ts
def get_value(by_name, feature_key):
    """
    Kann entweder:
      - str:   "heating.sensors.temperature.outside"
      - tuple: ("heating.compressors.0.statistics", "starts")  -> Unter-Property
    """
    # (A) Einfacher string: wie bisher inkl. Alternativen
    if isinstance(feature_key, str):
        hit = by_name.get(feature_key)
        if hit is not None:
            return hit["value"]
        for alt in ALTERNATES.get(feature_key, []):
            if alt in by_name:
                return by_name[alt]["value"]
        return None

    # (B) Tupel: (basis_feature, sub_property)
    if isinstance(feature_key, tuple) and len(feature_key) == 2:
        base_key, subprop = feature_key
        # direkter Treffer oder Alternative des Basis-Features
        hit = by_name.get(base_key)
        if hit is None:
            for alt in ALTERNATES.get(base_key, []):
                if alt in by_name:
                    hit = by_name[alt]
                    break
        if not hit:
            return None

        props = hit.get("properties") or {}
        # Unter-Property suchen – Viessmann verpackt oft so:
        # props["starts"] = {"value": 123, "timestamp": "..."}
        # props["hours"]  = {"value": 456.7, ...}
        raw = props.get(subprop)
        if isinstance(raw, dict):
            # typische Form: {"value": x, "unit": "..."}
            return raw.get("value")
        # manche liefern direkt Zahl/Bool
        return raw

    return None

def _prop_value(props, key):
    v = props.get(key)
    if isinstance(v, dict):
        return v.get("value")
    return v

def compressor_status(by_name, poll_minutes: int = 5):
    """
    Liefert 1 (=an) oder 0 (=aus), robust aus mehreren Quellen.
    """
    # 1) Direkte elektrische Leistung (W)
    for k in (
        "heating.compressors.0.sensors.power",
        "heating.heatPump.compressors.0.sensors.power",
        "heating.compressor.0.sensors.power",
    ):
        hit = by_name.get(k)
        if hit:
            w = hit.get("value")
            if isinstance(w, (int, float)):
                return 1 if w > 5 else 0

    # 2) Last/Modulation (%)
    for k in (
        "heating.compressors.0.statistics.load",
        "heating.heatPump.compressors.0.statistics.load",
        "heating.compressor.0.statistics.load",
    ):
        hit = by_name.get(k)
        if hit:
            load = hit.get("value")
            if isinstance(load, (int, float)):
                return 1 if load > 0 else 0

    # 3) "power"/"operating"/"running" Flags
    for k in (
        "heating.compressors.0.power",
        "heating.compressors.0.operating",
        "heating.compressors.0.running",
        "heating.heatPump.compressors.0.power",
    ):
        hit = by_name.get(k)
        if hit:
            v = hit.get("value")
            if isinstance(v, bool):
                return 1 if v else 0
            if isinstance(v, (int, float)):
                # falls Prozent/Level (0..100): >0 => an
                return 1 if v > 0 else 0
            if isinstance(v, str):
                return 1 if v.lower() in ("on", "true", "running", "active") else 0

    # 4) Fallback über Stunden-Delta ist in main leichter, weil wir dort die Vorzeile kennen
    return None  # unbekannt