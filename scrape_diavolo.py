from curl_cffi import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import re

URL = "https://www.carync.gov/recreation-enjoyment/parks-greenways-environment/parks/middle-creek-school-park/diavolo-new-hope-disc-golf-course"

def scrape_schedule():
    response = requests.get(URL, impersonate="chrome")
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # The site layout changes frequently, so we grab all page text directly
    content = soup.body.text if soup.body else soup.get_text()
    
    # Extract the year (it's often explicitly mentioned like "2026 Schedule")
    year_match = re.search(r'(202\d)\s+Schedule', content, re.IGNORECASE)
    if not year_match:
        year_match = re.search(r'(202\d)', content)
        
    year = year_match.group(1) if year_match else str(datetime.now().year)

    c = Calendar()
    
    # Regex to match: 01/04 | Open Flex | CADL Winter Singles League
    # Or: 04/30 | Closed Course| (4pm–10pm) TRIPLES NIGHT!
    pattern = r'(\d{2}/\d{2})\s*\|\s*([^|]+)\|\s*([^\n\r]+)'
    
    matches = re.findall(pattern, content)
    
    if not matches:
        print("Could not find any scheduled events matching the expected format.")
        return
    
    for date_str, status, description in matches:
        e = Event()
        
        # Combine date and year
        full_date = f"{date_str}/{year}"
        try:
            date_obj = datetime.strptime(full_date, "%m/%d/%Y")
        except ValueError:
            # Fallback in case of parsing errors
            continue
        
        e.name = f"Diavolo: {status.strip()}"
        e.begin = date_obj.replace(hour=8) # Default to morning
        e.description = description.strip()
        e.make_all_day()
        
        # Check for specific times in the status or description
        time_match = re.search(r'(\d+(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d+(?::\d{2})?\s*(?:am|pm))', status + " " + description, re.IGNORECASE)
        if time_match:
            # You could further refine this to set specific event hours
            e.description += f"\nScheduled Time: {time_match.group(1)}"
            
        c.events.append(e)

    with open('diavolo_schedule.ics', 'w') as f:
        f.writelines(c.serialize_iter())
    print(f"Success! Created calendar with {len(matches)} events.")

if __name__ == "__main__":
    scrape_schedule()
