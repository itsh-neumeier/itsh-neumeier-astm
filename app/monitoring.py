import csv
import os
import re
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ASTERISK_LOG = Path(os.getenv("ASTERISK_LOG", "/var/log/asterisk/full"))
ASTERISK_CDR = Path(os.getenv("ASTERISK_CDR", "/var/log/asterisk/cdr-csv/Master.csv"))


def digits_only(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


@dataclass
class ProviderNumberStatus:
    id: int
    did_plus: str
    trunk: str
    registration: str
    contact: str
    endpoint: str
    online: bool
    last_error: str
    history: list[dict[str, str]]


def run_asterisk(command: str, timeout: int = 8) -> str:
    try:
        result = subprocess.run(
            ["asterisk", "-rx", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.stdout or result.stderr or "").strip()
    except Exception as exc:
        return f"Asterisk unavailable: {exc}"


def parse_registration_status(output: str, registration_name: str) -> tuple[str, str]:
    status = "unknown"
    detail = ""
    for line in output.splitlines():
        if registration_name not in line:
            continue
        detail = line.strip()
        lowered = detail.lower()
        if "rejected" in lowered:
            status = "rejected"
        elif "unregistered" in lowered:
            status = "unregistered"
        elif "not" in lowered and "registered" in lowered:
            status = "unregistered"
        elif "registered" in lowered:
            status = "registered"
        elif "trying" in lowered:
            status = "trying"
        break
    return status, detail


def parse_named_status(output: str, token: str) -> tuple[str, str]:
    status = "unknown"
    detail = ""
    for line in output.splitlines():
        if token not in line:
            continue
        detail = line.strip()
        lowered = detail.lower()
        if any(word in lowered for word in ("unavail", "unreachable", "rejected", "offline")):
            status = "offline"
        elif any(word in lowered for word in ("avail", "available", "reachable", "in use")):
            status = "online"
        elif "not in use" in lowered:
            status = "online"
        break
    return status, detail


def read_cdr_rows(path: Path = ASTERISK_CDR, limit: int = 500) -> list[dict[str, str]]:
    if not path.exists():
        return []

    columns = [
        "accountcode",
        "src",
        "dst",
        "dcontext",
        "clid",
        "channel",
        "dstchannel",
        "lastapp",
        "lastdata",
        "start",
        "answer",
        "end",
        "duration",
        "billsec",
        "disposition",
        "amaflags",
        "uniqueid",
        "userfield",
        "sequence",
    ]
    rows: deque[dict[str, str]] = deque(maxlen=limit)
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for raw in csv.reader(handle):
                if not raw:
                    continue
                padded = raw + [""] * max(0, len(columns) - len(raw))
                rows.append(dict(zip(columns, padded)))
    except OSError:
        return []
    return list(rows)


def calls_for_number(cdr_rows: list[dict[str, str]], did_plus: str, limit: int = 20) -> list[dict[str, str]]:
    number_digits = digits_only(did_plus)
    matches: deque[dict[str, str]] = deque(maxlen=limit)
    for row in cdr_rows:
        searchable = " ".join(str(value) for value in row.values())
        if number_digits and number_digits in digits_only(searchable):
            direction = "outbound" if "outbound" in row.get("userfield", "") else "inbound"
            if "->" not in row.get("userfield", "") and row.get("dst") and number_digits in digits_only(row["dst"]):
                direction = "inbound"
            matches.append(
                {
                    "start": row.get("start", ""),
                    "direction": direction,
                    "src": row.get("src", ""),
                    "dst": row.get("dst", ""),
                    "duration": row.get("duration", "0"),
                    "billsec": row.get("billsec", "0"),
                    "disposition": row.get("disposition", ""),
                    "userfield": row.get("userfield", ""),
                }
            )
    return list(reversed(matches))


def tail_file(path: Path = ASTERISK_LOG, lines: int = 250) -> str:
    if not path.exists():
        return f"Log file not found: {path}"
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return "".join(deque(handle, maxlen=lines)).rstrip()
    except OSError as exc:
        return f"Cannot read log file {path}: {exc}"


def build_monitoring_snapshot(store: Any) -> dict[str, Any]:
    numbers = [dict(row) for row in store.list_rows("numbers")]
    settings = store.get_settings()
    registrations_output = run_asterisk("pjsip show registrations")
    contacts_output = run_asterisk("pjsip show contacts")
    endpoints_output = run_asterisk("pjsip show endpoints")
    cdr_rows = read_cdr_rows()
    provider_statuses: list[ProviderNumberStatus] = []

    registration_enabled = settings.get("provider_use_registration", "yes") == "yes"
    for index, number in enumerate(numbers, start=1):
        trunk = f"leonet-out-{index}"
        registration_name = f"{trunk}-reg"
        registration, registration_detail = parse_registration_status(
            registrations_output, registration_name
        )
        contact, contact_detail = parse_named_status(contacts_output, f"{trunk}-aor")
        endpoint, endpoint_detail = parse_named_status(endpoints_output, trunk)
        if not registration_enabled:
            registration = "disabled"
        online = registration == "registered" or contact == "online" or endpoint == "online"
        last_error = ""
        if registration in {"rejected", "unregistered"}:
            last_error = registration_detail
        elif contact == "offline":
            last_error = contact_detail
        elif endpoint == "offline":
            last_error = endpoint_detail
        provider_statuses.append(
            ProviderNumberStatus(
                id=number["id"],
                did_plus=number["did_plus"],
                trunk=trunk,
                registration=registration,
                contact=contact,
                endpoint=endpoint,
                online=online,
                last_error=last_error,
                history=calls_for_number(cdr_rows, number["did_plus"]),
            )
        )

    latest_calls = sorted(
        [
            {
                "start": row.get("start", ""),
                "src": row.get("src", ""),
                "dst": row.get("dst", ""),
                "duration": row.get("duration", "0"),
                "billsec": row.get("billsec", "0"),
                "disposition": row.get("disposition", ""),
                "userfield": row.get("userfield", ""),
            }
            for row in cdr_rows[-50:]
        ],
        key=lambda row: row["start"],
        reverse=True,
    )
    return {
        "provider_statuses": provider_statuses,
        "latest_calls": latest_calls,
        "raw": {
            "registrations": registrations_output,
            "contacts": contacts_output,
            "endpoints": endpoints_output,
        },
        "log": tail_file(lines=250),
    }
