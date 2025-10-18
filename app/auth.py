import os, json, time, base64, hashlib, threading, webbrowser
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import httpx
from .config import CLIENT_ID, REDIRECT_URI, AUTH_URL, TOKEN_URL, SCOPES

TOKENS_FILE = "tokens.json"

def _gen_pkce():
    v = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    d = hashlib.sha256(v.encode()).digest()
    c = base64.urlsafe_b64encode(d).rstrip(b"=").decode()
    return v, c

def _callback_server():
    parsed = urlparse(REDIRECT_URI)
    host, port, path = parsed.hostname or "0.0.0.0", parsed.port or 53682, parsed.path
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path != path: self.send_response(404); self.end_headers(); return
            qs = parse_qs(urlparse(self.path).query)
            if "code" in qs:
                self.send_response(200); self.end_headers()
                self.wfile.write(b'Auth ok - Fenster schliessen.')
                self.server.auth_code = qs["code"][0]
            else:
                self.send_response(400); self.end_headers()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
    httpd = HTTPServer((host, port), Handler); httpd.auth_code = None; httpd.serve_forever()
    return httpd.auth_code

def _save_tokens(t): open(TOKENS_FILE,"w").write(json.dumps(t))
def _load_tokens(): 
    try: return json.loads(open(TOKENS_FILE).read())
    except: return None

def _is_expired(t): return time.time() > t.get("expires_at", 0) - 30

def get_client():
    t = _load_tokens()
    if not t:
        v, c = _gen_pkce()
        params = {"client_id": CLIENT_ID,"redirect_uri": REDIRECT_URI,"response_type": "code","code_challenge": c,"code_challenge_method": "S256","scope": SCOPES}
        webbrowser.open(f"{AUTH_URL}?{urlencode(params)}")
        code = _callback_server()
        r = httpx.post(TOKEN_URL, data={"grant_type":"authorization_code","client_id":CLIENT_ID,"redirect_uri":REDIRECT_URI,"code_verifier":v,"code":code}, timeout=30)
        r.raise_for_status()
        data = r.json()
        t = {"access_token": data["access_token"], "refresh_token": data.get("refresh_token"), "expires_at": time.time()+data.get("expires_in",3600)}
        _save_tokens(t)
    elif _is_expired(t):
        r = httpx.post(TOKEN_URL, data={"grant_type":"refresh_token","client_id":CLIENT_ID,"refresh_token":t["refresh_token"]}, timeout=30)
        r.raise_for_status()
        data = r.json(); t["access_token"]=data["access_token"]; t["expires_at"]=time.time()+data.get("expires_in",3600)
        if "refresh_token" in data: t["refresh_token"]=data["refresh_token"]
        _save_tokens(t)
    return httpx.Client(timeout=30, headers={"Authorization": f"Bearer {t['access_token']}"})
