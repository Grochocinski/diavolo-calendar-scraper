from pathlib import Path

import pytest

from parse_schedule import _fixup_ics, _parse_time, parse_schedule, VTIMEZONE_NEW_YORK

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_HTML = FIXTURES_DIR / "sample_schedule.html"


class TestParseTime:
    def test_simple_pm(self) -> None:
        assert _parse_time("4pm") == (16, 0)

    def test_simple_am(self) -> None:
        assert _parse_time("4am") == (4, 0)

    def test_noon(self) -> None:
        """12pm is noon, not midnight."""
        assert _parse_time("12pm") == (12, 0)

    def test_midnight(self) -> None:
        """12am is midnight (hour 0), not noon."""
        assert _parse_time("12am") == (0, 0)

    def test_with_minutes_pm(self) -> None:
        assert _parse_time("4:30pm") == (16, 30)

    def test_with_minutes_am(self) -> None:
        assert _parse_time("12:30am") == (0, 30)

    def test_uppercase(self) -> None:
        assert _parse_time("4PM") == (16, 0)

    def test_strips_whitespace(self) -> None:
        assert _parse_time("  4pm  ") == (16, 0)

    def test_invalid_returns_none(self) -> None:
        assert _parse_time("not a time") is None

    def test_empty_returns_none(self) -> None:
        assert _parse_time("") is None

    def test_no_period_returns_none(self) -> None:
        """A bare number without am/pm is not a valid time."""
        assert _parse_time("4") is None


class TestFixupIcs:
    def _minimal_ics(self, vtimezone: str = "", extra_body: str = "") -> str:
        return (
            "BEGIN:VCALENDAR\r\n"
            "PRODID:-//test//test//EN\r\n"
            "VERSION:2.0\r\n"
            f"{vtimezone}"
            f"{extra_body}"
            "END:VCALENDAR\r\n"
        )

    def test_tzid_leading_slash_removed(self) -> None:
        vtimezone = "BEGIN:VTIMEZONE\r\nTZID:America/New_York\r\nEND:VTIMEZONE\r\n"
        ics = self._minimal_ics(vtimezone=vtimezone, extra_body=(
            "BEGIN:VEVENT\r\n"
            "DTSTART;TZID=/America/New_York:20260115T160000\r\n"
            "DTEND;TZID=/America/New_York:20260115T220000\r\n"
            "END:VEVENT\r\n"
        ))
        result = _fixup_ics(ics, "America/New_York")
        assert "TZID=/America/New_York" not in result
        assert "TZID=America/New_York" in result

    def test_vtimezone_replaced_with_standard_block(self) -> None:
        vtimezone = (
            "BEGIN:VTIMEZONE\r\n"
            "TZID:America/New_York\r\n"
            "BEGIN:STANDARD\r\n"
            "TZOFFSETFROM:-0400\r\n"
            "TZOFFSETTO:-0500\r\n"
            "END:STANDARD\r\n"
            "END:VTIMEZONE\r\n"
        )
        result = _fixup_ics(self._minimal_ics(vtimezone=vtimezone), "America/New_York")
        assert VTIMEZONE_NEW_YORK in result
        # The input STANDARD block had no DTSTART; the canonical one does.
        # If replacement worked, the bare BEGIN:STANDARD\r\nTZOFFSETFROM sequence is gone.
        assert "BEGIN:STANDARD\r\nTZOFFSETFROM" not in result

    def test_xwr_properties_moved_after_prodid(self) -> None:
        vtimezone = "BEGIN:VTIMEZONE\r\nTZID:America/New_York\r\nEND:VTIMEZONE\r\n"
        extra = (
            "X-WR-CALNAME:Diavolo Disc Golf\r\n"
            "X-WR-TIMEZONE:America/New_York\r\n"
        )
        ics = self._minimal_ics(vtimezone=vtimezone, extra_body=extra)
        result = _fixup_ics(ics, "America/New_York")
        prodid_pos = result.index("PRODID:")
        xwr_pos = result.index("X-WR-")
        version_pos = result.index("VERSION:")
        assert prodid_pos < xwr_pos < version_pos


class TestParseSchedule:
    def test_all_day_event(self, tmp_path: Path) -> None:
        """01/04 Open Flex has no time range and should be an all-day event."""
        ics_path = tmp_path / "output.ics"
        parse_schedule(SAMPLE_HTML, ics_path)
        content = ics_path.read_text()
        assert "20260104" in content
        assert "VALUE=DATE" in content

    def test_closed_course_event(self, tmp_path: Path) -> None:
        """03/21 Closed Course should appear in the summary."""
        ics_path = tmp_path / "output.ics"
        parse_schedule(SAMPLE_HTML, ics_path)
        content = ics_path.read_text()
        assert "20260321" in content
        assert "Closed Course" in content

    def test_timed_event(self, tmp_path: Path) -> None:
        """05/07 (4pm-10pm) should produce explicit DTSTART/DTEND timestamps."""
        ics_path = tmp_path / "output.ics"
        parse_schedule(SAMPLE_HTML, ics_path)
        content = ics_path.read_text()
        assert "20260507T160000" in content
        assert "20260507T220000" in content

    def test_middle_creek_course_detection(self, tmp_path: Path) -> None:
        """Events ending with '| Middle Creek' should use the Middle Creek course."""
        ics_path = tmp_path / "output.ics"
        parse_schedule(SAMPLE_HTML, ics_path)
        content = ics_path.read_text()
        assert "Middle Creek" in content
        assert "151 Middle Creek Park Ave" in content

    def test_plain_text_status_parsed(self, tmp_path: Path) -> None:
        """07/22 has 'Open Flex' as plain text (no span) and should still parse."""
        ics_path = tmp_path / "output.ics"
        parse_schedule(SAMPLE_HTML, ics_path)
        content = ics_path.read_text()
        assert "20260722" in content

    def test_overnight_event_end_advances_one_day(self, tmp_path: Path) -> None:
        """08/27 (4pm-12am): end time 12am is before start, so it should roll to next day."""
        ics_path = tmp_path / "output.ics"
        parse_schedule(SAMPLE_HTML, ics_path)
        content = ics_path.read_text()
        assert "20260827T160000" in content
        assert "20260828T000000" in content

    def test_no_events_exits_nonzero(self, tmp_path: Path) -> None:
        """An HTML page with no schedule rows should exit with a non-zero code."""
        empty_html = tmp_path / "empty.html"
        empty_html.write_text("<html><body><p>No schedule here.</p></body></html>")
        ics_path = tmp_path / "output.ics"
        with pytest.raises(SystemExit) as exc_info:
            parse_schedule(empty_html, ics_path)
        assert exc_info.value.code != 0
