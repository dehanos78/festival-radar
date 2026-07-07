#!/usr/bin/env python3
"""
Genereert festival-radar.ics uit:
  1. data/festivals.json  (Viktor's curated shortlist)
  2. de live Firestore 'events'-collectie (community-tips)

De agenda bevat:
  - een all-day VEVENT per festival met een bekende datum
  - een los VEVENT "Kaartverkoop: <naam>" met melding, zodra ticketSaleStart bekend is

Alleen Python-stdlib. Draaien:  python3 scripts/build_ics.py
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FESTIVALS_JSON = os.path.join(HERE, "data", "festivals.json")
OUT_ICS = os.path.join(HERE, "festival-radar.ics")

FIREBASE_PROJECT = "festival-radar-2718a"
FIRESTORE_URL = (
    f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}"
    "/databases/(default)/documents/events?pageSize=300"
)

ZONE_LABEL = {"near": "Voor de deur", "road": "Roadtrip", "bucket": "Bucketlist"}
STATUS_LABEL = {"go": "te scoren", "watch": "in de gaten", "gone": "uitverkocht / resale"}


def esc(text):
    """Escape volgens RFC 5545 voor TEXT-waarden."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold(line):
    """Vouw regels > 75 octetten (RFC 5545)."""
    out = []
    raw = line.encode("utf-8")
    while len(raw) > 74:
        # zoek veilige split-positie op byte-grens
        cut = 74
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n".join(out)


def d(datestr):
    """YYYY-MM-DD -> date, of None."""
    try:
        return datetime.strptime(datestr, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def fetch_firestore_events():
    """Haal community-events op via de publieke Firestore REST API."""
    try:
        with urllib.request.urlopen(FIRESTORE_URL, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - netwerk mag nooit de build breken
        print(f"[waarschuwing] Firestore niet bereikbaar: {e}", file=sys.stderr)
        return []

    events = []
    for doc in data.get("documents", []):
        fields = doc.get("fields", {})
        get = lambda k: fields.get(k, {}).get("stringValue", "")
        doc_id = doc.get("name", "").rsplit("/", 1)[-1]
        events.append(
            {
                "id": "community-" + doc_id,
                "name": get("name"),
                "zone": get("zone") or "near",
                "status": get("status") or "watch",
                "where": get("where"),
                "when": get("when"),
                "start": get("date") or None,
                "end": get("date") or None,
                "tickets": get("tickets"),
                "by": get("by"),
                "ticketSaleStart": None,
                "community": True,
            }
        )
    return events


STAMP = "20260101T000000Z"  # deterministisch tijdstempel (uit festivals.json 'updated'); voorkomt commit-ruis in de auto-sync


def vevent(uid, dtstart, dtend, summary, description, all_day=True, alarms=None):
    now = STAMP
    lines = ["BEGIN:VEVENT", f"UID:{uid}@festival-radar", f"DTSTAMP:{now}"]
    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{dtstart:%Y%m%d}")
        lines.append(f"DTEND;VALUE=DATE:{dtend:%Y%m%d}")
    else:
        lines.append(f"DTSTART:{dtstart:%Y%m%dT%H%M%S}")
        lines.append(f"DTEND:{dtend:%Y%m%dT%H%M%S}")
    lines.append(f"SUMMARY:{esc(summary)}")
    if description:
        lines.append(f"DESCRIPTION:{esc(description)}")
    for trigger in alarms or []:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{esc(summary)}",
            f"TRIGGER:{trigger}",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def build():
    global STAMP
    with open(FESTIVALS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    festivals = data["festivals"]
    upd = str(data.get("updated", "")).replace("-", "")
    if len(upd) == 8 and upd.isdigit():
        STAMP = upd + "T000000Z"

    events = list(festivals) + fetch_firestore_events()

    body = []
    n_fest = n_sale = 0
    for ev in events:
        zone = ZONE_LABEL.get(ev.get("zone"), "")
        status = STATUS_LABEL.get(ev.get("status"), "")
        start = d(ev.get("start"))
        # festival-event (all-day)
        if start:
            end = d(ev.get("end")) or start
            desc_parts = [
                p
                for p in [
                    ev.get("where"),
                    f"Reistijd {ev['travel']}" if ev.get("travel") else "",
                    f"Status: {status}" if status else "",
                    ev.get("tickets"),
                    f"Getipt door {ev['by']}" if ev.get("by") else "",
                    ev.get("url"),
                ]
                if p
            ]
            prefix = "♪ " if not ev.get("community") else "★ "
            label = ev["name"] + (f" · {ev['edition']}" if ev.get("edition") else "")
            body += vevent(
                ev["id"],
                start,
                end + timedelta(days=1),  # DTEND is exclusief bij all-day
                f"{prefix}{label}" + (f" · {zone}" if zone else ""),
                " — ".join(desc_parts),
            )
            n_fest += 1

        # losse feesten van een venue (bv. Woodstock69) — elk een eigen agenda-item
        for i, sub in enumerate(ev.get("subEvents") or []):
            sdate = d(sub.get("date"))
            if not sdate:
                continue
            sub_desc = " — ".join(p for p in [
                ev.get("where"), sub.get("note"), ev.get("url")] if p)
            body += vevent(
                f"{ev['id']}-sub{i}-{sdate:%Y%m%d}",
                sdate,
                sdate + timedelta(days=1),
                f"♪ {ev['name']} · {sub.get('name', '')}",
                sub_desc,
            )
            n_fest += 1

        # kaartverkoop-event (met melding) zodra bekend
        sale = d(ev.get("ticketSaleStart"))
        if sale:
            sale_dt = datetime(sale.year, sale.month, sale.day, 10, 0)
            body += vevent(
                ev["id"] + "-sale",
                sale_dt,
                sale_dt + timedelta(minutes=15),
                f"🎟️ Kaartverkoop start: {ev['name']}",
                f"Kaartverkoop opent voor {ev['name']} ({ev.get('where','')}). "
                f"{ev.get('tickets','')}",
                all_day=False,
                alarms=["-P1D", "-PT1H"],  # dag ervoor + uur ervoor
            )
            n_sale += 1

    now = STAMP
    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//festival-radar//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Festival Radar",
        "X-WR-TIMEZONE:Europe/Amsterdam",
        "X-WR-CALDESC:Vik's shortlist festivals + kaartverkoop-meldingen",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
        f"X-BUILT:{now}",
        *body,
        "END:VCALENDAR",
    ]

    with open(OUT_ICS, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(fold(l) for l in cal) + "\r\n")

    print(f"✓ {OUT_ICS}")
    print(f"  {n_fest} festival-events, {n_sale} kaartverkoop-meldingen")


if __name__ == "__main__":
    build()
