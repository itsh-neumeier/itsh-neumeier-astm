# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung folgt [SemVer](https://semver.org/lang/de/).

## [0.1.0] - 2026-06-03

### Added

- Initiale Docker-AIO-Lösung mit Asterisk und WebGUI.
- GHCR-Veröffentlichung als `ghcr.io/itsh-neumeier/itsh-neumeier-astm`.
- Debian-basiertes Image mit Asterisk 20 LTS aus offiziellem Source-Tarball.
- Portainer Stack-Datei für direkte GHCR-Deployments mit Host-Networking.
- 1-Click-Provisioning für UniFi Talk Rufnummern mit Inbound- und Outbound-Routing.
- Dropdown für Video-Fähigkeit bei SIP-Clients.
- Inline-Editing für Rufnummern, SIP-Clients, Inbound-Routen und Outbound-Routen.
- Multilingualer WebGUI-Support Deutsch/Englisch mit Flaggen-Umschaltung im Header.
- Login mit PBKDF2-Passworthash und signierter Session-Cookie.
- SQLite-State für Provider, Rufnummern, SIP-Clients und Routing.
- Generator für `pjsip.conf`, `extensions.conf`, UniFi-Talk-Zusammenfassung und Security Notes.
- Backup vor dem Überschreiben produktiver Asterisk-Konfiguration.
- Docker Compose Setup mit persistenten Volumes.
- GitHub Actions Workflow für Python-Smoke-Test und Docker-Build.
