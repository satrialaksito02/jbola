import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from bs4 import BeautifulSoup
import warnings
import logging
from collections import defaultdict
from datetime import datetime, timedelta
import pytz

# Suppress all warnings and logging
warnings.filterwarnings("ignore")
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('webdriver_manager').setLevel(logging.WARNING)
logging.getLogger('WDM').setLevel(logging.WARNING)

TARGET_LEAGUES = [
    "Champions League", "Europa League", "Conference League",
    "Premier League", "La Liga", "Serie A", "Bundesliga", 
    "Ligue 1", "Primeira Liga", "Copa del Rey", 
    "DFB Pokal", "FA Cup", "Coppa Italia"
]

def get_next_day_gmt7():
    """Get next day's date in GMT+7 timezone formatted as YYYY-MM-DD"""
    gmt7 = pytz.timezone('Asia/Jakarta')  # GMT+7
    now = datetime.now(gmt7)
    next_day = now + timedelta(days=1)
    return next_day.strftime("%Y-%m-%d")

def load_original_channels():
    """Load original channel names from OG_channel.txt"""
    try:
        with open('OG_channel.txt', 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print("Warning: OG_channel.txt not found. Using current channel names.")
        return None

def load_channels():
    """Load current channel names and map to original names"""
    with open('channel.txt', 'r', encoding='utf-8') as f:
        current_channels = [line.strip() for line in f.readlines() if line.strip()]
    
    original_channels = load_original_channels()
    channel_dict = {}
    original_names = {}
    
    for idx, channel in enumerate(current_channels):
        country_match = re.search(r'\((.*?)\)', channel)
        country = country_match.group(1).lower() if country_match else None
        
        # Get original name if available
        original_name = original_channels[idx] if original_channels and idx < len(original_channels) else channel
        
        # Normalize for matching
        normalized = re.sub(r'\(.*?\)', '', channel).strip().lower()
        key = (normalized, country.lower() if country else None)
        
        channel_dict[key] = original_name  # Store original name
        original_names[channel] = original_name  # Map current to original
    
    return channel_dict, original_names

def group_sequential_channels(channels):
    """Group sequential channels like Viaplay 1, Viaplay 2 into Viaplay 1-3"""
    channel_groups = defaultdict(list)
    original_names = {}  # To store original formatting
    
    for channel in channels:
        # Extract base name and number while preserving original spacing
        match = re.match(r'^(.*?)\s*(\d+)$', channel.strip())
        if match:
            base, num = match.groups()
            # Store the original base name (with correct spacing)
            original_base = base.strip()
            channel_groups[original_base].append(int(num))
            # Keep track of original formatting
            if original_base not in original_names:
                original_names[original_base] = base
        else:
            channel_groups[channel].append(0)  # Non-numbered channels
    
    result = []
    for base, numbers in channel_groups.items():
        if len(numbers) > 1 and all(n > 0 for n in numbers):
            # Handle numbered channels
            numbers = sorted(list(set(numbers)))  # Remove duplicates and sort
            if numbers == list(range(min(numbers), max(numbers)+1)):
                # Sequential numbers - use original formatting
                original_base = original_names.get(base, base)
                result.append(f"{original_base} {min(numbers)}-{max(numbers)}")
            else:
                # Non-sequential numbers
                original_base = original_names.get(base, base)
                for num in sorted(numbers):
                    result.append(f"{original_base} {num}")
        else:
            # Non-numbered or single-numbered channels
            if numbers[0] > 0:
                original_base = original_names.get(base, base)
                result.append(f"{original_base} {numbers[0]}")
            else:
                result.append(base)
    
    return result

def get_html_selenium(url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    service = Service(
        ChromeDriverManager().install(),
        service_args=['--verbose'],
        log_path='NUL'
    )
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        time.sleep(5)
        return driver.page_source
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return None
    finally:
        try:
            driver.quit()
        except:
            pass

def extract_channels_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    channels = []
    
    rows = soup.find_all('tr')
    for row in rows:
        country_span = row.find('span', class_='flag')
        country = country_span.text.strip().lower() if country_span else None
        
        channel_links = row.find_all('a', {'class': ['black', 'nou']})
        for link in channel_links:
            channel_name = link.text.strip()
            channels.append((channel_name.lower(), country))
    
    return channels

def process_match(match, channel_dict):
    print(f"\nProcessing match: {match['match']}")
    print(f"League: {match['league']}")
    
    html_content = get_html_selenium(match['url'])
    if not html_content:
        print("Failed to fetch HTML content")
        return match
    
    html_channels = extract_channels_from_html(html_content)
    matched_channels = set()
    
    for html_name, html_country in html_channels:
        if html_country:
            key = (html_name.lower(), html_country.lower())
            if key in channel_dict:
                matched_channels.add(channel_dict[key])
                continue
        
        key = (html_name.lower(), None)
        if key in channel_dict:
            matched_channels.add(channel_dict[key])
    
    if matched_channels:
        # Group sequential channels
        grouped_channels = group_sequential_channels(matched_channels)
        updated_match = match.copy()
        updated_match['channels'] = ", ".join(grouped_channels)
        print(f"Updated channels: {updated_match['channels']}")
        return updated_match
    else:
        print("No matching channels found")
        return match

def main():
    # Get the next day's date in GMT+7
    next_day = get_next_day_gmt7()
    input_filename = f"matches_{next_day}.json"
    
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            matches = json.load(f)
    except FileNotFoundError:
        print(f"Error: {input_filename} not found.")
        return
    
    if not matches:
        print("No matches found in the JSON file.")
        return
    
    channel_dict, _ = load_channels()
    
    processed_matches = []
    for match in matches:
        # If the match is in target leagues, process it; otherwise leave as-is
        if any(league in match['league'] for league in TARGET_LEAGUES):
            processed_match = process_match(match, channel_dict)
            processed_matches.append(processed_match)
        else:
            processed_matches.append(match)
    
    output_filename = f"matches_processed_{next_day}.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(processed_matches, f, indent=2, ensure_ascii=False)
    
    print(f"\nProcessing complete. Results saved to {output_filename}")
    print(f"Total matches processed: {len(processed_matches)}")
if __name__ == "__main__":
    main()