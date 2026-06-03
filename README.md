# ITSH Neumeier Asterisk SIP-Trunk Management AIO

All-in-one Docker-Lösung für Asterisk PJSIP, SIP-Trunk-Konfiguration, UniFi Talk Gateway und WebGUI-Management mit Login.

Die WebGUI bildet die Kernlogik des ursprünglichen Shell/TUI-Scripts ab:

- Provider-/Trunk-Defaults für LEONET und freie Providerwerte
- Mehrere öffentliche Rufnummern mit SIP-Zugangsdaten
- UniFi Talk Custom Provider Gateway über `external_talk` Port `6767`
- Interne SIP-Clients/Nebenstellen inklusive Caller-ID und optionaler IP-ACL
- Inbound- und Outbound-Routing
- Vorschau, Backup, Schreiben von `pjsip.conf` und `extensions.conf`
- Asterisk Reload und Statusanzeige aus der WebGUI

## Schnellstart

```bash
cp .env.example .env
# ADMIN_PASSWORD in .env setzen
docker compose --env-file .env up -d --build
```

WebGUI:

```text
http://localhost:8080
```

Standard-Benutzer:

```text
admin
```

Wenn `ADMIN_PASSWORD` beim ersten Start nicht gesetzt ist, generiert der Container ein Passwort und schreibt es in die Logs:

```bash
docker logs itsh-neumeier-astm
```

## Ports

| Zweck | Port |
| --- | --- |
| WebGUI | `8080/tcp` |
| SIP PJSIP | `5060/udp` |
| RTP Audio/Video | `10000-20000/udp` |

Für produktive Installationen muss die Firewall SIP strikt einschränken:

- `5060/udp` nur von Provider-IP-Netzen, UniFi Talk und bekannten SIP-Clients
- `10000-20000/udp` nur von benötigten Gegenstellen
- WebGUI nur aus Administrationsnetzen oder hinter Reverse Proxy/VPN

## Docker und SIP/NAT

SIP ist empfindlich gegenüber NAT. Die WebGUI enthält optionale Transport-Felder:

- `Externe Signaling-Adresse`
- `Externe Media-Adresse`
- `Lokales Netz`

Wenn Asterisk über Docker Bridge läuft und Gegenstellen nicht im selben Netz liegen, diese Werte passend setzen. Auf Linux kann alternativ ein Host-Network-Deployment sinnvoll sein.

## Datenhaltung

`docker-compose.yml` legt persistente Volumes an:

- `astm-data`: SQLite-Datenbank, Session-Secret
- `astm-backups`: Backups und UniFi-/Security-Zusammenfassungen
- `astm-asterisk`: produktive Asterisk-Konfiguration

## Workflow

1. WebGUI öffnen und einloggen.
2. Unter `Provider` Asterisk-IP, UniFi-IP, Provider-Daten und NAT-Werte prüfen.
3. Unter `Rufnummern` SIP-Trunk-Nummern und Credentials pflegen.
4. Unter `Clients` interne Nebenstellen anlegen.
5. Unter `Routing` Inbound-/Outbound-Routen setzen.
6. Unter `Apply` Konfiguration prüfen und anwenden.
7. UniFi-Hinweise unter `UniFi` in UniFi Talk Custom Provider übertragen.

## Lokale Entwicklung

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
DATA_DIR=.tmp-data ASTERISK_ETC=.tmp-asterisk BACKUP_DIR=.tmp-backups ADMIN_PASSWORD=admin uvicorn app.main:app --reload
```

Tests:

```bash
python -m unittest discover
```

## Versionierung

Die aktuelle Version steht in `VERSION`. Änderungen werden in `CHANGELOG.md` dokumentiert. Releases sollten SemVer verwenden:

- `MAJOR`: inkompatible Daten-/Konfigurationsänderungen
- `MINOR`: neue Funktionen
- `PATCH`: Bugfixes
