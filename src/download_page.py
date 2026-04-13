import json
from pathlib import Path

from curl_cffi import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text())


def download_page() -> Path:
    url = CONFIG["schedule_url"]
    out_path = ROOT / CONFIG["html_file"]
    print(f"Downloading {url} ...")
    response = requests.get(url, impersonate="chrome")
    response.raise_for_status()
    out_path.write_text(response.text, encoding="utf-8")
    print(f"Saved to {out_path}")
    return out_path


if __name__ == "__main__":
    download_page()
