# 🪊 VissmannCollect – Viessmann Wärmepumpen-Datenlogger

> **VissmannCollect** liest Messwerte einer Viessmann Wärmepumpe (Vitocal / Vitodens / Heat Pump) über die
> neue Viessmann IoT API (v2) aus und speichert sie in einer SQL-Datenbank.
>
> Ziel ist die langfristige Analyse des **Takt-Verhaltens** (Starts / Laufzeiten / Temperaturen),
> um den Betrieb der Wärmepumpe effizienter zu gestalten.

---

## 🚀 Features

* 🔐 **OAuth2 PKCE Login** gegen die neue Viessmann IoT API v2
* 🔄 **Automatischer Token-Refresh** (keine manuelle Anmeldung mehr nötig)
* 🧩 **Flexible Feature-Erkennung** – liest dynamisch alle Sensor-Features
* 💾 **Speichert Werte in MySQL** (Tabelle `vitodata`)
* 📈 Unterstützte Messgrößen:

  * Außentemperatur
  * Vorlauf / Rücklauf (Heizkreis 0 + 1)
  * Warmwasser oben / Solltemperatur
  * Sekundärkreis Vorlauf
  * Kompressor Start-Zähler, Betriebsstunden, Status (an/aus)
* ⚙️ **Docker-Compose-Setup** mit MySQL + App
* 📁 Automatischer **CSV-Dump aller Features** für Diagnosezwecke
* 🕐 **Konfigurierbarer Abruf-Intervall** (Standard: alle 5 Minuten)
* 🧮 Basis-SQL-Abfragen für Taktanalyse (Starts pro Tag, Laufzeiten etc.)

---

## 🧱 Projektstruktur

```text
vissmanncollect/
├─ app/
│  ├─ auth.py          # OAuth2-Login, Token-Handling
│  ├─ config.py        # .env-Konfiguration & Konstanten
│  ├─ db.py            # SQLAlchemy-Engine + Insert-Funktion
│  ├─ features.py      # Feature-Mapping & Parser-Logik
│  ├─ viessmann.py     # API-Endpunkte für Installationen / Features
│  └─ main.py          # Entry-Point (Poll-Loop)
├─ sql/
│  └─ vitodata.sql     # DB-Schema für Tabelle vitodata
├─ out/                # (wird erzeugt) CSV-Exports aller Features
├─ requirements.txt
├─ docker-compose.yml
├─ Dockerfile
└─ .env.example
```

---

## ⚙️ Installation & Setup

### 1️⃣ Viessmann Developer-Client anlegen

1. Gehe zu [https://developer.viessmann.com](https://developer.viessmann.com)
2. Erstelle eine neue **App / Client**

   * Typ: Web App
   * Redirect URI: `http://localhost:53682/callback`
3. Notiere deine **Client ID** (keine Client Secret nötig)

---

### 2️⃣ `.env` erstellen

```env
CLIENT_ID=<deine_client_id>
REDIRECT_URI=http://localhost:53682/callback
GATEWAY_SERIAL=<Dein Gateway Serial>
DEVICE_ID=0
POLL_MINUTES=5

# MySQL (Docker-Compose erstellt User & DB automatisch)
MYSQL_DATABASE=vitocal
MYSQL_USER=vitoapp
MYSQL_PASSWORD=<starkes_passwort>
MYSQL_ROOT_PASSWORD=<root_pw>

DATABASE_URL=mysql+pymysql://vitoapp:<starkes_passwort>@db:3306/vitocal
```

---

### 3️⃣ Start per Docker Compose

```bash
docker compose up --build
```

* Beim ersten Start öffnet sich dein Browser zur Viessmann-Anmeldung.
  Nach erfolgreicher Authentifizierung wird `tokens.json` erzeugt.
* Anschließend pollt die App automatisch alle 5 Minuten und schreibt Werte in die DB.

---

## 🗄️ Datenbankstruktur (`vitodata.sql`)

```sql
CREATE TABLE vitodata (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  installation_id VARCHAR(64),
  gateway_serial VARCHAR(64),
  device_id VARCHAR(16),
  aussentemperatur FLOAT,
  vorlauftemperatur_hk FLOAT,
  vorlauftemperatur_fb FLOAT,
  ruecklauftemperatur FLOAT,
  sekundaerkreis_vorlauf FLOAT,
  warmwasser_oben FLOAT,
  warmwasser_soll FLOAT,
  kompressor_anzahl_starts INT,
  kompressor_laufzeit_h FLOAT,
  kompressor_status TINYINT(1)
);
```

---

## 🧩 Datenabfrage (Beispiele)

### Letzte Werte

```sql
SELECT * FROM vitodata ORDER BY timestamp DESC LIMIT 10;
```

### Takt-Analyse (Starts / Laufzeit / Intervall)

```sql
WITH rows AS (
  SELECT
    id, timestamp,
    kompressor_anzahl_starts AS starts,
    kompressor_laufzeit_h    AS hours,
    LAG(kompressor_anzahl_starts) OVER (ORDER BY id) AS prev_starts,
    LAG(kompressor_laufzeit_h)    OVER (ORDER BY id) AS prev_hours
  FROM vitodata
)
SELECT
  timestamp,
  (starts - prev_starts) AS starts_delta,
  (hours - prev_hours)   AS hours_delta,
  TIMESTAMPDIFF(MINUTE, LAG(timestamp) OVER (ORDER BY id), timestamp) AS minutes_since_prev
FROM rows
WHERE prev_starts IS NOT NULL
ORDER BY timestamp DESC;
```

---

## ⚙️ Anpassungen

* **Poll-Intervall:**
  In `.env` → `POLL_MINUTES=5` (Standard = 5 Minuten)

* **Feature-Mapping erweitern:**
  In `app/features.py` → `FEATURES` und `ALTERNATES`

* **DB-User ändern:**
  `.env` und `docker-compose.yml` (env Variablen `MYSQL_USER` / `MYSQL_PASSWORD`)

* **CSV-Dump aktivieren:**
  Automatisch → Dateien liegen in `./out/features-YYYYMMDD-HHMMSSZ.csv`

---

## 🧮 Beispiel-Output

```text
[i] Starte neuen Poll-Durchlauf...
[i] 193 Features indexiert – gewünschte Auswahl:

  aussentemperatur         : 7.9
  vorlauftemperatur_hk     : 29.7
  ruecklauftemperatur      : 25.0
  warmwasser_oben          : 43.8
  warmwasser_soll          : 47.0
  kompressor_anzahl_starts : 1253
  kompressor_laufzeit_h    : 412.6
  kompressor_status        : 0
[✓] In DB gespeichert.
```

---

## 🧠 Weiterentwicklung

* 📊 Jupyter-Notebook oder Grafana-Dashboard für Taktanalyse
* 🧮 Automatische Berechnung von Taktfrequenz & mittlerer Laufzeit
* 🔔 Benachrichtigung bei Kurzzyklen (zu häufigem Takten)
* ☁️ Optionaler Export nach InfluxDB oder TimescaleDB

---

## 🪪 Lizenz

**MIT License**
(c) 2025 Matthias Staud / GitHub-Handle

Siehe [`LICENSE`](LICENSE)

---

## ❤️ Dank an

* [Viessmann Developer Portal](https://developer.viessmann.com) – für die API & Dokumentation
* [FastAPI](https://fastapi.tiangolo.com) / [SQLAlchemy](https://www.sqlalchemy.org) / [PyMySQL](https://pypi.org/project/PyMySQL/)
* OpenAI GPT Assistenz beim Code-Refactoring & Dokumentation

---
