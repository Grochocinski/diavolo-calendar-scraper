import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from ics import Calendar, Event

DEFAULT_HTML = Path(__file__).resolve().parent / "diavolo_page.html"
DEFAULT_ICS = Path(__file__).resolve().parent / "diavolo_schedule.ics"


def parse_schedule(html_path: Path = DEFAULT_HTML, ics_path: Path = DEFAULT_ICS):
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

    entries: list[tuple[str, str, str]] = []
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
            # Everything after the status is description.  Some entries
            # have a trailing location field (e.g. "Middle Creek") we drop.
            desc_fields = fields[2:]
            if desc_fields and desc_fields[-1].lower() in ("middle creek",):
                desc_fields = desc_fields[:-1]
            description = " ".join(desc_fields)
            entries.append((date_str, status, description))

    if not entries:
        print("Could not find any scheduled events matching the expected format.")
        sys.exit(1)

    cal = Calendar()

    for date_str, status, description in entries:
        status = status.strip().replace("\xa0", " ")
        description = description.strip().replace("\xa0", " ") if description else ""

        try:
            date_obj = datetime.strptime(f"{date_str}/{year}", "%m/%d/%Y")
        except ValueError:
            continue

        event = Event()
        event.summary = f"Diavolo: {status}"
        event.begin = date_obj.replace(hour=8)
        if description:
            event.description = description
        event.make_all_day()

        time_match = re.search(
            r"(\d+(?::\d{2})?\s*(?:am|pm)?\s*[-\u2013]\s*\d+(?::\d{2})?\s*(?:am|pm))",
            f"{status} {description}",
            re.IGNORECASE,
        )
        if time_match:
            event.description = (event.description or "") + f"\nScheduled Time: {time_match.group(1)}"

        cal.events.append(event)

    ics_path.write_text(cal.serialize())
    print(f"Success! Wrote {len(cal.events)} events to {ics_path}")


if __name__ == "__main__":
    parse_schedule()
