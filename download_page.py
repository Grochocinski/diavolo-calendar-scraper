from curl_cffi import requests

URL = "https://www.carync.gov/recreation-enjoyment/parks-greenways-environment/parks/middle-creek-school-park/diavolo-new-hope-disc-golf-course"

def download_page():
    print(f"Downloading contents from {URL}...")
    response = requests.get(URL, impersonate="chrome")
    response.raise_for_status()  # Check if the request was successful
    
    with open('diavolo_page_contents.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
        
    print("Successfully saved page source to diavolo_page_contents.html!")

if __name__ == "__main__":
    download_page()