import os

POLL_MINUTES = int(os.getenv("POLL_MINUTES", "5"))  # Default: 5 Minuten
import time
from .auth import get_client
from .config import GATEWAY_SERIAL, DEVICE_ID
from .db import insert_row
from .viessmann import get_installations, get_features
from .features import FEATURES, index_features, get_value, compressor_status


def run():
    with get_client() as client:
        # Installation holen (erste reicht)
        insts = get_installations(client)
        if not insts: print("Keine Installationen."); return
        inst_id = insts[0].get("installation",{}).get("id") or insts[0].get("id") or insts[0].get("installationId")

        gw_serial = GATEWAY_SERIAL or os.environ.get("GATEWAY_SERIAL")
        dev_id = DEVICE_ID or os.environ.get("DEVICE_ID")
        assert gw_serial and dev_id, "GATEWAY_SERIAL/DEVICE_ID fehlen."

        feats = get_features(client, inst_id, gw_serial, dev_id)
        by_name = index_features(feats)
        # Kompressor-Status robust bestimmen (1/0)
        status = compressor_status(by_name, poll_minutes=5)

        # --- Diagnose: Welche Properties hat das Statistics-Feature wirklich?
        for key in ("heating.compressors.0.statistics", "heating.compressors.1.statistics"):
            item = by_name.get(key)
            if item:
                props = item.get("properties") or {}
                print(f"[diag] {key} -> properties keys: {list(props.keys())[:20]}")

        for label, feature_key in FEATURES.items():
            if label == "kompressor_status":
                # wir zeigen unseren berechneten Status statt des Rohwertes
                print(f"  {label:25s}: {status if status is not None else '(unbekannt)'}")
                continue
            val = get_value(by_name, feature_key)
            print(f"  {label:25s}: {val if val is not None else '(nicht vorhanden)'}")



        # Konsolen-Ausgabe wie gehabt
        print(f"[i] {len(by_name)} Features indexiert – gewünschte Auswahl:\n")
        for label, feature_key in FEATURES.items():
            val = get_value(by_name, feature_key)
            print(f"  {label:25s}: {val if val is not None else '(nicht vorhanden)'}")

        # ==== DB: Zeile aufbauen (nur vorhandene Spalten setzen) ====
        row = {
            "installation_id": inst_id,
            "gateway_serial": gw_serial,
            "device_id": str(dev_id),
        }
        # Mappe nur die Spalten, die in der Tabelle existieren (siehe vitodata.sql)
        # (timestamp hat DEFAULT CURRENT_TIMESTAMP in DB)
        for col, feature_key in FEATURES.items():
            if col == "kompressor_status":
                if status is not None:
                    row[col] = int(status)  # 1/0 in DB
                continue
            v = get_value(by_name, feature_key)
            if v is not None:
                row[col] = v

        # Beispiel (falls du später willst): Kompressorwerte hinzufügen, wenn vorhanden:
        # for k in ("heating.compressors.0.statistics.starts","heating.compressors.0.statistics.hours","heating.compressors.0.status"):
        #   ...

        insert_row(row)
        print("\n[✓] In DB gespeichert.")

def run_loop():
    from .main import run
    while True:
        try:
            print(f"[i] Starte neuen Poll-Durchlauf...")
            run()
        except Exception as e:
            print("[X] Fehler beim Poll:", e)
        print(f"[i] Warte {POLL_MINUTES} Minuten bis zum nächsten Durchlauf...")
        time.sleep(POLL_MINUTES * 60)

if __name__ == "__main__":
    run_loop()

