import os, json, time, base64, hashlib, threading, webbrowser
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

import httpx
from dotenv import load_dotenv

# ===== Konfiguration aus .env =====
load_dotenv()
CLIENT_ID = os.environ.get("CLIENT_ID")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:53682/callback")
assert CLIENT_ID, "CLIENT_ID fehlt in .env"
assert REDIRECT_URI, "REDIRECT_URI fehlt in .env"

IAM_BASE = "https://iam.viessmann-climatesolutions.com/idp/v2"
API_BASE = "https://api.viessmann-climatesolutions.com"
AUTH_URL = f"{IAM_BASE}/authorize"
TOKEN_URL = f"{IAM_BASE}/token"
SCOPES = "IoT User offline_access"

TOKENS_FILE = "../tokens.json"
FEATURES = {
    "aussentemperatur": "heating.sensors.temperature.outside",
    "vorlauftemperatur_hk": "heating.circuits.0.temperature",
    "vorlauftemperatur_fb": "heating.circuits.1.temperature",
    "ruecklauftemperatur": "heating.sensors.temperature.return",
    "sekundaerkreis_vorlauf": "heating.secondaryCircuit.sensors.temperature.supply",
    "warmwasser_oben": "heating.dhw.sensors.temperature.dhwCylinder.top",
    "warmwasser_soll": "heating.dhw.temperature.main",
    "kompressor_anzahl_starts": "heating.compressors.0.statistics.starts",
    "kompressor_laufzeit_h": "heating.compressors.0.statistics.hours",
    "kompressor_status": "heating.compressors.0.status",
}

# ===== PKCE =====
def gen_pkce():
    verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge

# ===== Mini-Callback-Server =====
class CallbackHandler(BaseHTTPRequestHandler):
    # Wird von OAuth-Redirect aufgerufen: /callback?code=...
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != urlparse(REDIRECT_URI).path:
            self.send_response(404); self.end_headers(); return
        qs = parse_qs(parsed.query)
        if "error" in qs:
            msg = f"OAuth-Fehler: {qs['error'][0]}"
            self.send_response(400); self.end_headers()
            self.wfile.write(msg.encode())
            self.server.oauth_error = msg
        elif "code" in qs:
            code = qs["code"][0]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"Auth ok. Du kannst dieses Fenster schliessen und zur Konsole wechseln.")
            self.server.auth_code = code
        else:
            self.send_response(400); self.end_headers()
            self.wfile.write(b"Kein Code erhalten.")
        # Server nach Antwort stoppen
        threading.Thread(target=self.server.shutdown, daemon=True).start()

def start_callback_server():
    # Port aus REDIRECT_URI lesen
    parsed = urlparse(REDIRECT_URI)
    host = parsed.hostname or "localhost"
    port = parsed.port or 53682
    httpd = HTTPServer((host, port), CallbackHandler)
    print(f"[i] Warte auf Callback unter {host}:{port} ...")
    httpd.auth_code = None
    httpd.oauth_error = None
    httpd.serve_forever()
    return httpd.auth_code, httpd.oauth_error

# ===== Token-Handling =====
def save_tokens(data):
    with open(TOKENS_FILE, "w") as f: json.dump(data, f)

def load_tokens():
    if not os.path.exists(TOKENS_FILE): return None
    with open(TOKENS_FILE, "r") as f: return json.load(f)

def is_expired(tokens):
    return time.time() > tokens.get("expires_at", 0) - 30

def refresh(tokens):
    if not tokens or "refresh_token" not in tokens:
        raise RuntimeError("Kein Refresh-Token vorhanden.")
    with httpx.Client(timeout=30) as client:
        r = client.post(TOKEN_URL, data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        })
    if r.status_code != 200:
        raise RuntimeError(f"Refresh fehlgeschlagen: {r.text}")
    data = r.json()
    tokens["access_token"] = data["access_token"]
    tokens["expires_at"] = time.time() + data.get("expires_in", 3600)
    if "refresh_token" in data:
        tokens["refresh_token"] = data["refresh_token"]
    save_tokens(tokens)
    return tokens

def obtain_tokens_interactive():
    verifier, challenge = gen_pkce()
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": SCOPES,
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"
    print("[i] Öffne Browser für Login...")
    webbrowser.open(auth_url)

    # lokalen Callback-Server blockierend starten
    code, oauth_error = start_callback_server()
    if oauth_error:
        raise RuntimeError(oauth_error)
    if not code:
        raise RuntimeError("Kein Code erhalten.")

    with httpx.Client(timeout=30) as client:
        r = client.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
            "code": code,
        })
    if r.status_code != 200:
        raise RuntimeError(f"Token-Antwort ungültig: {r.text}")
    data = r.json()
    tokens = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),
        "expires_at": time.time() + data.get("expires_in", 3600),
    }
    save_tokens(tokens)
    print("[✓] Tokens gespeichert.")
    return tokens

def get_client():
    tokens = load_tokens()
    if not tokens:
        tokens = obtain_tokens_interactive()
    elif is_expired(tokens):
        print("[i] Access-Token abgelaufen – versuche Refresh...")
        tokens = refresh(tokens)

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return httpx.Client(timeout=30, headers=headers)

# ===== API-Helper =====
def get_installations(client):
    url = f"{API_BASE}/iot/v2/equipment/installations"
    r = client.get(url); r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        print("[warn] /installations lieferte eine leere Liste.")
    else:
        # zeige das erste Objekt einmal grob an (zur Diagnose)
        print("[debug] installation[0] keys:", list(data[0].keys()))
    return data

def _extract_installation_id(item: dict):
    # mehrere mögliche Strukturen abdecken
    return (
        item.get("installation", {}).get("id")
        or item.get("id")
        or item.get("installationId")
    )

def get_gateways_devices(client, installation_id):
    # Gateways holen (Struktur robust parsen)
    url = f"{API_BASE}/iot/v2/equipment/installations/{installation_id}/gateways"
    r = client.get(url); r.raise_for_status()
    gw_list = r.json().get("data", [])
    if gw_list:
        print("[debug] gateway[0] keys:", list(gw_list[0].keys()))
    items = []
    for g in gw_list:
        # manche Antworten haben {"gateway": {...}}, andere die Felder direkt
        gw = g.get("gateway") or g
        gw_serial = gw.get("serial") or gw.get("gatewaySerial") or gw.get("id")
        if not gw_serial:
            print("[warn] Kein gateway serial in:", g)
            continue

        # Devices unterhalb des Gateways holen
        r2 = client.get(f"{API_BASE}/iot/v2/equipment/installations/{installation_id}/gateways/{gw_serial}/devices")
        r2.raise_for_status()
        dev_list = r2.json().get("data", [])
        if dev_list:
            print("[debug] device[0] keys:", list(dev_list[0].keys()))
        for d in dev_list:
            dv = d.get("device") or d
            dev_id = dv.get("id") or dv.get("deviceId")
            if not dev_id:
                print("[warn] Kein device id in:", d)
                continue
            items.append((gw_serial, dev_id))
    return items

def get_gateways_devices(client, installation_id):
    url = f"{API_BASE}/iot/v2/equipment/installations/{installation_id}/gateways"
    r = client.get(url); r.raise_for_status()
    items = []
    for g in r.json().get("data", []):
        gw_serial = g["gateway"]["serial"]
        r2 = client.get(f"{API_BASE}/iot/v2/equipment/installations/{installation_id}/gateways/{gw_serial}/devices")
        r2.raise_for_status()
        for d in r2.json().get("data", []):
            items.append((gw_serial, d["device"]["id"]))
    return items

def get_features(client, installation_id, gw_serial, device_id):
    url = f"{API_BASE}/iot/v2/features/installations/{installation_id}/gateways/{gw_serial}/devices/{device_id}/features"
    r = client.get(url); r.raise_for_status()
    return r.json().get("data", [])

def _extract_name_and_props(item):
    """
    Akzeptiert Formen wie:
    - {"feature": "heating...","properties": {...}, ...}
    - {"feature": {"name": "heating...", "properties": {...}}, ...}
    - {"name": "heating...", "properties": {...}}
    Gibt (name, props_dict) zurück.
    """
    if not isinstance(item, dict):
        return None, {}

    name = None
    props = {}

    feat = item.get("feature")
    if isinstance(feat, dict):
        # v1/v2-Variante mit Objekt
        name = feat.get("name")
        # Properties können entweder am Top-Level oder im feature-Objekt liegen
        props = item.get("properties") or feat.get("properties") or {}
    elif isinstance(feat, str):
        # v2-Variante wie in deinem Dump: feature ist direkt ein String
        name = feat
        props = item.get("properties") or {}
    else:
        # Fallback auf "name"
        name = item.get("name")
        props = item.get("properties") or {}

    return name, props


def _extract_value_from_props(props):
    """
    Holt einen sinnvollen Wert aus den Properties.
    Viele Viessmann-Werte sitzen als props["value"]["value"] (mit Einheit).
    Diese Funktion arbeitet robust und holt das 'value' ggf. rekursiv.
    """
    if not isinstance(props, dict) or not props:
        return None

    def _unwrap(v):
        # entpackt Strukturen wie {"value": 12.3, "unit": "celsius"} → 12.3
        if isinstance(v, dict):
            if "value" in v:
                return _unwrap(v["value"])
            # wenn kein "value", aber nur ein primitives Feld drin ist:
            for k2, v2 in v.items():
                if not isinstance(v2, (dict, list)):
                    return v2
        return v

    # Bevorzugte Schlüssel zuerst:
    for key in ("value", "status", "temperature", "level", "state", "active"):
        if key in props:
            return _unwrap(props[key])

    # manchmal liegt der primitive Wert direkt oben
    if "value" in props and not isinstance(props["value"], dict):
        return props["value"]

    return None


def index_features(features_raw):
    """
    Baut Dict: { feature_name: {"value": x, "properties": {...}, "raw": item} }
    und ignoriert Einträge ohne Name.
    """
    by = {}
    for item in features_raw:
        name, props = _extract_name_and_props(item)
        if not name:
            continue
        val = _extract_value_from_props(props)
        by[name] = {"value": val, "properties": props, "raw": item}
    return by


# ===== Hauptablauf =====
def main():
    try:
        with get_client() as client:
            installation_id = None

            # Wir versuchen zunächst, Installationen zu holen,
            # brauchen sie aber nur, um deine Gateway/Device-Kombination zu validieren
            print("[i] Rufe Installationen ab...")
            installations = get_installations(client)
            if not installations:
                print("Keine Installationen gefunden."); return

            # Nehmen einfach die erste Installation (meist nur eine vorhanden)
            first = installations[0]
            installation_id = (
                first.get("installation", {}).get("id")
                or first.get("id")
                or first.get("installationId")
            )
            print(f"[✓] Installation: {installation_id}")

            # --- feste Werte aus .env ---
            gw_serial = os.environ.get("GATEWAY_SERIAL")
            dev_id = os.environ.get("DEVICE_ID")
            assert gw_serial and dev_id, "Bitte GATEWAY_SERIAL und DEVICE_ID in .env setzen."

            print(f"[✓] Verwende Gateway={gw_serial}  Device={dev_id}")

            #feats = get_features(client, installation_id, gw_serial, dev_id)
            feats = get_features(client, installation_id, gw_serial, dev_id)
            print("[debug] Beispiel-Item:", feats[0])
            print(f"[i] {len(feats)} Features gefunden – kleine Auswahl:\n")
            # robust indexieren
            by_name = index_features(feats)
            print(f"[i] {len(by_name)} Features indexiert – gewünschte Auswahl:\n")

            # Optionale Alternativen für verbreitete Namensvarianten (falls du willst)
            ALTERNATES = {
                "heating.sensors.temperature.outside": [
                    "heating.sensors.temperature.outdoor"
                ],
                "heating.circuits.0.temperature": [
                    "heating.circuits.0.sensors.temperature.supply"
                ],
                "heating.circuits.1.temperature": [
                    "heating.circuits.1.sensors.temperature.supply"
                ],
                "heating.dhw.sensors.temperature.dhwCylinder.top": [
                    "heating.dhw.sensors.temperature.hotWaterStorage.top"
                ],
            }

            def get_value_for(feature_key):
                # direkter Treffer?
                hit = by_name.get(feature_key)
                if hit is not None:
                    return hit["value"]

                # Alternativen probieren
                for alt in ALTERNATES.get(feature_key, []):
                    if alt in by_name:
                        return by_name[alt]["value"]
                return None


            # Deine FEATURES-Liste ausgeben (Name -> Wert)
            for label, feature_key in FEATURES.items():
                val = get_value_for(feature_key)
                if val is None:
                    print(f"  {label:25s}: (nicht vorhanden)")
                else:
                    print(f"  {label:25s}: {val}")

            print("\n[✓] Fertig.")
    except Exception as e:
        print("[X] Fehler:", e)

if __name__ == "__main__":
    main()
