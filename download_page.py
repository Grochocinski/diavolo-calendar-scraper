from pathlib import Path

from curl_cffi import requests

URL = "https://www.carync.gov/recreation-enjoyment/parks-greenways-environment/parks/middle-creek-school-park/diavolo-new-hope-disc-golf-course"
DEFAULT_OUT = Path(__file__).resolve().parent / "diavolo_page.html"


def download_page(out_path: Path = DEFAULT_OUT) -> Path:
    print(f"Downloading {URL} ...")
    response = requests.get(URL, impersonate="chrome")
    response.raise_for_status()
    out_path.write_text(response.text, encoding="utf-8")
    print(f"Saved to {out_path}")
    return out_path


if __name__ == "__main__":
    download_page()
