import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from ics import Calendar, Event
from ics.contentline import ContentLine

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text())


def _parse_time(raw: str) -> tuple[int, int] | None:
    """Parse '4pm', '12:30am', etc. into (hour, minute)."""
    raw = raw.strip().lower()
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", raw)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    period = m.group(3)
    if period == "am" and hour == 12:
        hour = 0
    elif period == "pm" and hour != 12:
        hour += 12
    return (hour, minute)


def parse_schedule(
    html_path: Path = ROOT / CONFIG["html_file"],
    ics_path: Path = ROOT / CONFIG["ics_file"],
):
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    page_text = soup.get_text()
    year_match = re.search(r"(202\d)\s+Schedule", page_text, re.IGNORECASE)
    if not year_match:
        year_match = re.search(r"(202\d)", page_text)
    year = year_match.group(1) if year_match else str(datetime.now().year)

    # Each schedule row lives in a <div> whose text starts with "MM/DD |".
    # The parent div groups several rows; extracting text with "|" as a
    # separator gives us pipe-delimited fields we can split on date
    # boundaries to recover individual entries.
    date_divs = soup.find_all(
        string=lambda t: t and re.match(r"\s*\d{2}/\d{2}\s*\|", t)
    )

    seen_parents: set[int] = set()
    raw_rows: list[str] = []
    for text_node in date_divs:
        parent = text_node.parent.parent
        pid = id(parent)
        if pid in seen_parents:
            continue
        seen_parents.add(pid)
        row_text = parent.get_text(separator="|")
        row_text = re.sub(r"\s+", " ", row_text)
        row_text = re.sub(r"\s*\|\s*", "|", row_text)
        row_text = row_text.strip("|").strip()
        raw_rows.append(row_text)

    courses = CONFIG["courses"]
    course_keys = {k for k in courses if k != CONFIG["default_course"]}

    entries: list[tuple[str, str, str, str]] = []
    for row in raw_rows:
        chunks = re.split(r"(?=\d{2}/\d{2}\|)", row)
        for chunk in chunks:
            fields = [f.strip() for f in chunk.split("|") if f.strip()]
            if len(fields) < 2 or not re.match(r"^\d{2}/\d{2}$", fields[0]):
                continue
            date_str = fields[0]
            status = fields[1]
            if not re.match(r"(?:Open|Closed)", status, re.IGNORECASE):
                continue
            desc_fields = fields[2:]
            course_key = CONFIG["default_course"]
            if desc_fields and desc_fields[-1].lower() in course_keys:
                course_key = desc_fields.pop().lower()
            description = " ".join(desc_fields)
            entries.append((date_str, status, description, course_key))

    if not entries:
        print("Could not find any scheduled events matching the expected format.")
        sys.exit(1)

    cal = Calendar()
    cal.extra.append(ContentLine(name="X-WR-CALNAME", value=CONFIG["calendar_name"]))
    cal.extra.append(ContentLine(name="X-WR-TIMEZONE", value=CONFIG["timezone"]))

    uid_counts: dict[str, int] = {}

    for date_str, status, description, course_key in entries:
        status = status.strip().replace("\xa0", " ")
        description = description.strip().replace("\xa0", " ") if description else ""

        try:
            date_obj = datetime.strptime(f"{date_str}/{year}", "%m/%d/%Y")
        except ValueError:
            continue

        course = courses[course_key]
        base_key = f"{date_obj.strftime('%Y-%m-%d')}|{course_key}"
        idx = uid_counts.get(base_key, 0)
        uid_counts[base_key] = idx + 1
        uid_input = f"{base_key}|{idx}"
        uid = hashlib.sha256(uid_input.encode()).hexdigest()[:16]

        event = Event()
        event.uid = f"{uid}@diavolo-calendar-scraper"
        event.summary = f"{course['name']}: {status}"
        event.location = f"{course['name']}, {course['address']}"

        time_pat = r"\(?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*[-\u2013]\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*\)?"
        time_match = re.search(time_pat, description, re.IGNORECASE)
        if time_match:
            start_time = _parse_time(time_match.group(1))
            end_time = _parse_time(time_match.group(2))
            if start_time is not None and end_time is not None:
                tz = ZoneInfo(CONFIG["timezone"])
                event.begin = date_obj.replace(hour=start_time[0], minute=start_time[1], tzinfo=tz)
                end_dt = date_obj.replace(hour=end_time[0], minute=end_time[1], tzinfo=tz)
                if end_dt <= event.begin:
                    end_dt += timedelta(days=1)
                event.end = end_dt
                description = re.sub(time_pat, " ", description, count=1, flags=re.IGNORECASE).strip()
            else:
                event.begin = date_obj.replace(hour=8)
                event.make_all_day()
        else:
            event.begin = date_obj.replace(hour=8)
            event.make_all_day()

        if description:
            event.description = description

        cal.events.append(event)

    output = cal.serialize()
    # The ics library uses non-standard TZID prefixes like
    # /ics.py/2020.1/America/New_York.  Normalize to bare IANA names.
    output = re.sub(r"TZID=/?[^:]*?/(America/[^:\r\n]+)", r"TZID=\1", output)
    output = re.sub(r"TZID:/?[^/\r\n]*/[^/\r\n]*/(America/[^\r\n]+)", r"TZID:\1", output)
    # Move X-WR-* properties to just after PRODID for RFC ordering.
    xwr_lines = re.findall(r"X-WR-[^\r\n]+", output)
    for line in xwr_lines:
        output = output.replace(line + "\r\n", "")
    xwr_block = "\r\n".join(xwr_lines) + "\r\n"
    prodid_end = output.index("\r\n", output.index("PRODID:")) + 2
    output = output[:prodid_end] + xwr_block + output[prodid_end:]
    ics_path.write_text(output)
    print(f"Success! Wrote {len(cal.events)} events to {ics_path}")


if __name__ == "__main__":
    parse_schedule()
