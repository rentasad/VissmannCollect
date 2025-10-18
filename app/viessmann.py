import httpx
from .config import API_BASE

def get_installations(client: httpx.Client):
    r = client.get(f"{API_BASE}/iot/v2/equipment/installations"); r.raise_for_status()
    return r.json().get("data", [])

def get_features(client: httpx.Client, installation_id, gateway_serial, device_id):
    url = f"{API_BASE}/iot/v2/features/installations/{installation_id}/gateways/{gateway_serial}/devices/{device_id}/features"
    r = client.get(url); r.raise_for_status()
    return r.json().get("data", [])
