# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung folgt [SemVer](https://semver.org/lang/de/).

## [0.1.0] - 2026-06-03

### Added

- Initiale Docker-AIO-Lösung mit Asterisk und WebGUI.
- GHCR-Veröffentlichung als `ghcr.io/itsh-neumeier/itsh-neumeier-astm`.
- Portainer Stack-Datei für direkte GHCR-Deployments.
- Login mit PBKDF2-Passworthash und signierter Session-Cookie.
- SQLite-State für Provider, Rufnummern, SIP-Clients und Routing.
- Generator für `pjsip.conf`, `extensions.conf`, UniFi-Talk-Zusammenfassung und Security Notes.
- Backup vor dem Überschreiben produktiver Asterisk-Konfiguration.
- Docker Compose Setup mit persistenten Volumes.
- GitHub Actions Workflow für Python-Smoke-Test und Docker-Build.
