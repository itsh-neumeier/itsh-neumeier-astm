# Mapping vom Shell/TUI-Script zur AIO-WebGUI

Das ursprüngliche Script arbeitet dialog-/whiptail-basiert und schreibt direkt in ein lokales System oder einen Proxmox-LXC. Diese AIO-Version verschiebt den Zustand in SQLite und macht die Schritte über eine WebGUI bedienbar.

## Übernommene Kernfunktionen

| Shell/TUI-Bereich | WebGUI-Bereich |
| --- | --- |
| Zielsystem lokal/LXC | Docker-AIO Container |
| UniFi Talk Parameter | `Provider` |
| Providerprofil / LEONET Defaults | `Provider` |
| Rufnummerntabelle | `Rufnummern` |
| SIP-Clients / Nebenstellen | `Clients` |
| Inbound-/Outbound-Routing | `Routing` |
| Config Review | `Apply` |
| Schreiben und Reload | `Apply` |
| UniFi Talk Zusammenfassung | `UniFi` |
| Security Notes | `/backups/itsh-astm-security-notes.txt` |

## Bewusste Architekturänderungen

- Kein `pct exec`: Asterisk läuft im selben Container.
- Kein `dialog`/`whiptail`: Bedienung erfolgt über HTML-Forms.
- Keine CSV-Dateien als primärer State: SQLite ist führend, Generatorausgabe ist deterministisch.
- Keine automatische Firewall-Konfiguration: Firewall bleibt Aufgabe des Hosts.
- Credentials liegen im persistenten Volume und werden nur für Asterisk-Konfiguration gerendert.

## Kompatibilitätshinweise

- Abschnittsnamen `leonet-out-N`, `leonet-in`, `unifi-talk` bleiben bewusst kompatibel mit dem Ursprungsscript.
- Dialplan-Kontexte `from-leonet`, `from-unifi`, `from-internal-client` bleiben erhalten.
- UniFi Talk nutzt weiterhin IP-Trust und Port `6767` Richtung `external_talk`.
