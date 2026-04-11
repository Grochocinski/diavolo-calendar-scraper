# Diavolo Calendar Scraper

Scrapes the [Diavolo at New Hope](https://www.carync.gov/recreation-enjoyment/parks-greenways-environment/parks/middle-creek-school-park/diavolo-new-hope-disc-golf-course) disc golf course schedule and produces an ICS calendar file.

A GitHub Actions workflow runs daily to keep `diavolo_schedule.ics` up to date.

## Subscribe in Google Calendar

1. Open [Google Calendar Settings > Add calendar > From URL](https://calendar.google.com/calendar/r/settings/addbyurl)
2. Paste this URL:

```
https://raw.githubusercontent.com/Grochocinski/diavolo-calendar-scraper/main/diavolo_schedule.ics
```

3. Click **Add calendar**.

Google Calendar polls the URL roughly every 12-24 hours, so updates will appear automatically.

## Local usage

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run python download_page.py   # fetch HTML to diavolo_page.html
uv run python parse_schedule.py  # parse HTML into diavolo_schedule.ics
```
