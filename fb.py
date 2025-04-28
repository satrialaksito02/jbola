import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
from datetime import datetime, timedelta

def time_to_sortable(time_str):
    """Convert time string to sortable format"""
    try:
        # Handle cases where time might be 'LIVE' or other non-time values
        if ':' in time_str:
            return datetime.strptime(time_str, '%H:%M').time()
        return datetime.strptime('23:59', '%H:%M').time()  # Put non-time entries at the end
    except ValueError:
        return datetime.strptime('23:59', '%H:%M').time()  # Fallback for invalid times

def get_html_selenium(url):
    """Primary method using Selenium to bypass Cloudflare"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Tambahkan opsi untuk menekan log yang tidak perlu
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    # Setup service untuk menekan output log
    service = Service(ChromeDriverManager().install())
    service.creationflags = 0x08000000  # CREATE_NO_WINDOW

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        time.sleep(5)  # Wait for page to load and Cloudflare challenge to complete
        return driver.page_source
    except Exception as e:
        print(f"Selenium request failed: {e}")
        return None
    finally:
        driver.quit()

def extract_matches(html_content):
    if not html_content:
        return []
        
    soup = BeautifulSoup(html_content, 'html.parser')
    matches = []
    current_league = None
    
    rows = soup.find_all('tr')
    
    for row in rows:
        # Check if it's a competition header row
        if 'sortable_comp' in row.get('class', []):
            league_span = row.find('span', class_=lambda x: x and 'flag' in x.split())
            if league_span:
                current_league = league_span.get_text(strip=True)
            else:
                comp_row = row.find('td', class_='r_comprow')
                current_league = comp_row.get_text(strip=True) if comp_row else "Unknown League"
            continue
        
        # Skip if it's not a match row
        time_cell = row.find('span', class_='timecell')
        if not time_cell:
            continue
            
        # Extract match details
        match_info = {
            'league': current_league if current_league else "Unknown League",
            'time': None,
            'sortable_time': None,  # Field baru untuk sorting
            'match': None,
            'channels': None,
        }
        
        # Extract time
        time_span = time_cell.find('span', class_='ts')
        if time_span and 'dv' in time_span.attrs:
            timestamp = int(time_span['dv']) / 1000
            match_time = datetime.fromtimestamp(timestamp)
            match_info['time'] = match_time.strftime('%H:%M')
            match_info['sortable_time'] = match_time.time()
        else:
            time_text = time_cell.get_text(strip=True)
            match_info['time'] = time_text
            match_info['sortable_time'] = time_to_sortable(time_text)

        # Extract match info
        match_cell = row.find('td', id='match')
        if match_cell:
            match_link = match_cell.find('a')
            if match_link:
                match_info['match'] = match_link.get_text(strip=True)
                match_info['url'] = "https://www.livesoccertv.com" + match_link['href']
            else:
                match_info['match'] = match_cell.get_text(strip=True)
        
        # Extract channels
        channels_div = row.find('div', class_='mchannels')
        if channels_div:
            channels = []
            for a in channels_div.find_all('a'):
                channel_name = a.get_text(strip=True)
                if 'flag' in a.get('class', []):
                    channel_name = a.get('title', channel_name).split('(')[0].strip()
                channels.append(channel_name)
            match_info['channels'] = ', '.join(channels)
        
        matches.append(match_info)
    
    return matches

def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    print(f"Data saved to {filename}")

def main():
    # Get current date in GMT+7 (add 7 hours to UTC)
    today = datetime.utcnow() + timedelta(hours=7)
    tomorrow = today + timedelta(days=1)
    date = tomorrow.strftime("%Y-%m-%d")
    url = f"https://www.livesoccertv.com/schedules/{date}/"
    json_filename = f"matches_{date}.json"
    
    print(f"Fetching matches for {date}...")
    
    html_content = get_html_selenium(url)
    
    if not html_content:
        print("Failed to fetch HTML content")
        return
    
    matches = extract_matches(html_content)
    
    if not matches:
        print("No matches found in the HTML")
        return
    
    # Sort matches by time
    sorted_matches = sorted(matches, key=lambda x: x['sortable_time'])
    
    # Remove the temporary sortable_time field before saving
    for match in sorted_matches:
        match.pop('sortable_time', None)
    
    save_to_json(sorted_matches, json_filename)
    
    print(f"\nFound {len(sorted_matches)} matches on {date} (sorted by time):")
    for match in sorted_matches[:10]:  # Show first 10 matches as sample
        print(f"{match['time']} - {match['match']} ({match['league']})")

if __name__ == "__main__":
    main()

