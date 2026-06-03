import os
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .security import hash_password, verify_password


DEFAULTS = {
    "app_title": "ITSH Neumeier - Asterisk SIP-Trunk Management",
    "asterisk_ip": "127.0.0.1",
    "unifi_ip": "192.168.10.1",
    "unifi_port": "6767",
    "unifi_range": "127.0.0.1/32",
    "external_signaling_address": "",
    "external_media_address": "",
    "local_net": "",
    "provider_display_name": "LEONET",
    "provider_registrar": "sip.leovoice.online",
    "provider_server_uri": "sip:sip.leovoice.online:5060",
    "provider_from_domain": "sip.leovoice.online",
    "provider_match_ip": "91.106.121.3/32",
    "provider_transport": "udp",
    "provider_outbound_proxy": "",
    "provider_use_registration": "yes",
}


class Store:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "astm.db"

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def init(self) -> str | None:
        generated_password = None
        with closing(self.connect()) as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS numbers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    did_plus TEXT NOT NULL UNIQUE,
                    sip_username TEXT NOT NULL,
                    sip_password TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    extension TEXT NOT NULL UNIQUE,
                    sip_username TEXT NOT NULL,
                    sip_password TEXT NOT NULL,
                    ip_acl TEXT NOT NULL DEFAULT '',
                    caller_id_plus TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    client_type TEXT NOT NULL DEFAULT 'generic',
                    video_enabled INTEGER NOT NULL DEFAULT 0,
                    audio_codecs TEXT NOT NULL DEFAULT 'alaw,ulaw',
                    video_codecs TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS routes_inbound (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    did_plus TEXT NOT NULL UNIQUE,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    ring_seconds INTEGER NOT NULL DEFAULT 45,
                    description TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS routes_outbound (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    number_id INTEGER NOT NULL REFERENCES numbers(id) ON DELETE CASCADE,
                    caller_id_plus TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    UNIQUE(source_type, source_id)
                );
                """
            )
            for key, value in DEFAULTS.items():
                con.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    (key, value),
                )

            user_count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if user_count == 0:
                username = os.getenv("ADMIN_USER", "admin")
                password = os.getenv("ADMIN_PASSWORD")
                if not password:
                    password = secrets.token_urlsafe(18)
                    generated_password = password
                con.execute(
                    "INSERT INTO users(username, password_hash) VALUES(?, ?)",
                    (username, hash_password(password)),
                )

            number_count = con.execute("SELECT COUNT(*) FROM numbers").fetchone()[0]
            if number_count == 0:
                con.execute(
                    """
                    INSERT INTO numbers(did_plus, sip_username, sip_password)
                    VALUES(?, ?, ?)
                    """,
                    ("+491234567890", "leo491234567890", "change-me"),
                )
            con.commit()
        return generated_password

    def authenticate(self, username: str, password: str) -> bool:
        with closing(self.connect()) as con:
            row = con.execute(
                "SELECT password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
        return bool(row and verify_password(password, row["password_hash"]))

    def get_settings(self) -> dict[str, str]:
        with closing(self.connect()) as con:
            rows = con.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def update_settings(self, values: dict[str, Any]) -> None:
        with closing(self.connect()) as con:
            for key, value in values.items():
                con.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(value)),
                )
            con.commit()

    def list_rows(self, table: str) -> list[sqlite3.Row]:
        allowed = {"numbers", "clients", "routes_inbound", "routes_outbound"}
        if table not in allowed:
            raise ValueError("invalid table")
        with closing(self.connect()) as con:
            return con.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()

    def add_number(self, did_plus: str, sip_username: str, sip_password: str) -> None:
        with closing(self.connect()) as con:
            con.execute(
                "INSERT INTO numbers(did_plus, sip_username, sip_password) VALUES(?, ?, ?)",
                (did_plus, sip_username, sip_password),
            )
            con.commit()

    def update_number(
        self, number_id: int, did_plus: str, sip_username: str, sip_password: str
    ) -> None:
        with closing(self.connect()) as con:
            con.execute(
                """
                UPDATE numbers
                SET did_plus = ?, sip_username = ?, sip_password = ?
                WHERE id = ?
                """,
                (did_plus, sip_username, sip_password, number_id),
            )
            con.commit()

    def get_number(self, number_id: int) -> sqlite3.Row | None:
        with closing(self.connect()) as con:
            return con.execute("SELECT * FROM numbers WHERE id = ?", (number_id,)).fetchone()

    def provision_unifi_number(self, number_id: int) -> sqlite3.Row:
        number = self.get_number(number_id)
        if not number:
            raise ValueError("number not found")

        with closing(self.connect()) as con:
            con.execute(
                """
                INSERT INTO routes_inbound(
                    did_plus, target_type, target_id, ring_seconds, description
                ) VALUES(?, 'unifi', 'unifi-talk', 60, '1-Click UniFi Talk inbound')
                ON CONFLICT(did_plus) DO UPDATE SET
                    target_type = excluded.target_type,
                    target_id = excluded.target_id,
                    ring_seconds = excluded.ring_seconds,
                    description = excluded.description
                """,
                (number["did_plus"],),
            )
            con.execute(
                """
                INSERT INTO routes_outbound(
                    source_type, source_id, number_id, caller_id_plus, description
                ) VALUES('unifi', 'unifi-talk', ?, ?, '1-Click UniFi Talk outbound')
                ON CONFLICT(source_type, source_id) DO UPDATE SET
                    number_id = excluded.number_id,
                    caller_id_plus = excluded.caller_id_plus,
                    description = excluded.description
                """,
                (number["id"], number["did_plus"]),
            )
            con.commit()
        return number

    def delete_row(self, table: str, row_id: int) -> None:
        allowed = {"numbers", "clients", "routes_inbound", "routes_outbound"}
        if table not in allowed:
            raise ValueError("invalid table")
        with closing(self.connect()) as con:
            con.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            con.commit()

    def add_client(self, values: dict[str, Any]) -> None:
        with closing(self.connect()) as con:
            con.execute(
                """
                INSERT INTO clients(
                    client_id, name, extension, sip_username, sip_password, ip_acl,
                    caller_id_plus, enabled, client_type, video_enabled, audio_codecs, video_codecs
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["client_id"],
                    values["name"],
                    values["extension"],
                    values["sip_username"],
                    values["sip_password"],
                    values.get("ip_acl", ""),
                    values.get("caller_id_plus", ""),
                    1 if values.get("enabled") else 0,
                    values.get("client_type", "generic"),
                    1 if values.get("video_enabled") else 0,
                    values.get("audio_codecs", "alaw,ulaw"),
                    values.get("video_codecs", ""),
                ),
            )
            con.commit()

    def update_client(self, client_id: int, values: dict[str, Any]) -> None:
        with closing(self.connect()) as con:
            con.execute(
                """
                UPDATE clients
                SET client_id = ?, name = ?, extension = ?, sip_username = ?,
                    sip_password = ?, ip_acl = ?, caller_id_plus = ?, enabled = ?,
                    client_type = ?, video_enabled = ?, audio_codecs = ?, video_codecs = ?
                WHERE id = ?
                """,
                (
                    values["client_id"],
                    values["name"],
                    values["extension"],
                    values["sip_username"],
                    values["sip_password"],
                    values.get("ip_acl", ""),
                    values.get("caller_id_plus", ""),
                    1 if values.get("enabled") else 0,
                    values.get("client_type", "generic"),
                    1 if values.get("video_enabled") else 0,
                    values.get("audio_codecs", "alaw,ulaw"),
                    values.get("video_codecs", ""),
                    client_id,
                ),
            )
            con.commit()

    def add_inbound_route(self, values: dict[str, Any]) -> None:
        with closing(self.connect()) as con:
            con.execute(
                """
                INSERT INTO routes_inbound(did_plus, target_type, target_id, ring_seconds, description)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    values["did_plus"],
                    values["target_type"],
                    values["target_id"],
                    int(values.get("ring_seconds") or 45),
                    values.get("description", ""),
                ),
            )
            con.commit()

    def update_inbound_route(self, route_id: int, values: dict[str, Any]) -> None:
        with closing(self.connect()) as con:
            con.execute(
                """
                UPDATE routes_inbound
                SET did_plus = ?, target_type = ?, target_id = ?,
                    ring_seconds = ?, description = ?
                WHERE id = ?
                """,
                (
                    values["did_plus"],
                    values["target_type"],
                    values["target_id"],
                    int(values.get("ring_seconds") or 45),
                    values.get("description", ""),
                    route_id,
                ),
            )
            con.commit()

    def add_outbound_route(self, values: dict[str, Any]) -> None:
        with closing(self.connect()) as con:
            con.execute(
                """
                INSERT INTO routes_outbound(source_type, source_id, number_id, caller_id_plus, description)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    values["source_type"],
                    values["source_id"],
                    int(values["number_id"]),
                    values.get("caller_id_plus", ""),
                    values.get("description", ""),
                ),
            )
            con.commit()

    def update_outbound_route(self, route_id: int, values: dict[str, Any]) -> None:
        with closing(self.connect()) as con:
            con.execute(
                """
                UPDATE routes_outbound
                SET source_type = ?, source_id = ?, number_id = ?,
                    caller_id_plus = ?, description = ?
                WHERE id = ?
                """,
                (
                    values["source_type"],
                    values["source_id"],
                    int(values["number_id"]),
                    values.get("caller_id_plus", ""),
                    values.get("description", ""),
                    route_id,
                ),
            )
            con.commit()

    def change_password(self, username: str, password: str) -> None:
        with closing(self.connect()) as con:
            con.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (hash_password(password), username),
            )
            con.commit()
