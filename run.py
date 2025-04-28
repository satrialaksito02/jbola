import os
import json
import schedule
import time
from datetime import datetime, timedelta
import pytz
import telebot
from fb import main as fetch_matches
from ch2 import main as process_matches

# Telegram Bot Configuration
BOT_TOKEN = '6664352428:AAEcDvinkqag-MxBBZT6p6861ZTg_vokffM'
CHANNEL_ID = '@jadwalsepakbolatv'  # e.g., '@football_schedule'

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Country flag emoji mapping
COUNTRY_FLAGS = {
    'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    'Spain': '🇪🇸',
    'Italy': '🇮🇹',
    'Germany': '🇩🇪',
    'France': '🇫🇷',
    'Netherlands': '🇳🇱',
    'Portugal': '🇵🇹',
    'Brazil': '🇧🇷',
    'Argentina': '🇦🇷',
    'UEFA': '🏆',
    'FIFA': '🌍',
    'Asia': '🌏',
    'Africa': '🌍',
    'South America': '🌎',
    'Australia': '🇦🇺',
    'Turkey': '🇹🇷',
    # Add more mappings as needed
}

def get_formatted_date():
    """Get formatted date for display (e.g., Thursday, April 04 2025)"""
    gmt7 = pytz.timezone('Asia/Jakarta')  # GMT+7
    now = datetime.now(gmt7)
    next_day = now + timedelta(days=1)
    return next_day.strftime("%A, %B %d %Y")

def format_match_message(match):
    """Format a single match into the desired Telegram message format"""
    message = (
        f"✦   {match['time']} | <b>{match['match']}</b>\n"
        f"📺  {match.get('channels', 'Not available')}\n"
    )
    return message

def group_matches_by_league(matches):
    """Group matches by their league/competition"""
    leagues = {}
    for match in matches:
        league = match.get('league', 'Other')
        if league not in leagues:
            leagues[league] = []
        leagues[league].append(match)
    return leagues

def get_country_flag(league_name):
    """Get country flag emoji based on league name"""
    for country, flag in COUNTRY_FLAGS.items():
        if country.lower() in league_name.lower():
            return flag
    return '⚽'  # Default football emoji if no country matched

def split_message(message, max_length=4096):
    """Split a long message into parts that fit Telegram's message length limit"""
    lines = message.split('\n')
    parts = []
    current_part = []
    current_length = 0

    for line in lines:
        line_length = len(line) + 1  # +1 for the newline character
        if current_length + line_length > max_length:
            parts.append('\n'.join(current_part))
            current_part = [line]
            current_length = line_length
        else:
            current_part.append(line)
            current_length += line_length

    if current_part:
        parts.append('\n'.join(current_part))

    return parts

def create_telegram_messages(matches):
    """Create Telegram messages with all matches grouped by league"""
    gmt7 = pytz.timezone('Asia/Jakarta')
    tomorrow = datetime.now(gmt7) + timedelta(days=1)
    
    # Create header message
    header = (
        "⚽ 𝙁𝙤𝙤𝙩𝙗𝙖𝙡𝙡 𝙈𝙖𝙩𝙘𝙝 𝙎𝙘𝙝𝙚𝙙𝙪𝙡𝙚 𝙁𝙞𝙭𝙩𝙪𝙧𝙚𝙨 ⚽\n"
        f"📅 {get_formatted_date()}\n\n"
        "⭐ Streaming bola paling lengkap pake 𝐌𝟑𝐔 𝐈𝐏𝐓𝐕! Cek di @lxdigital\n"
        f"🌐 Info siaran TV lengkap: <a href=\"https://www.livesoccertv.com/schedules/{tomorrow.strftime('%Y-%m-%d')}/\">klik di sini!</a>\n"
        "────────────────────────────────\n"
    ) 

    # Group matches by league
    leagues = group_matches_by_league(matches)
    league_messages = []

    for league, league_matches in leagues.items():
        # Add league header with country flag
        flag = get_country_flag(league)
        league_message = f"\n{flag} <b>{league}</b>\n"
        league_message += "────────────────\n"

        # Add matches for this league
        for i, match in enumerate(league_matches):
            league_message += format_match_message(match)
            # Only add single newline between matches, double newline between leagues
            if i < len(league_matches) - 1:
                league_message += "\n"

        league_messages.append(league_message)

    # Combine all parts
    full_message = header + '\n'.join(league_messages)  # Double newline between leagues
    
    # Split the message if it's too long
    return split_message(full_message)

def send_daily_schedule():
    """Main function to fetch, process, and send matches"""
    try:
        print("Starting daily schedule process...")
        
        # Step 1: Fetch matches using fb.py
        fetch_matches()
        
        # Step 2: Process matches using ch2.py
        process_matches()
        
        # Get the next day's date in GMT+7 for filename
        gmt7 = pytz.timezone('Asia/Jakarta')
        next_day = datetime.now(gmt7) + timedelta(days=1)
        date_str = next_day.strftime("%Y-%m-%d")
        processed_filename = f"matches_processed_{date_str}.json"
        
        # Load processed matches
        with open(processed_filename, 'r', encoding='utf-8') as f:
            matches = json.load(f)
        
        # Create and send messages
        messages = create_telegram_messages(matches)
        for msg in messages:
            bot.send_message(CHANNEL_ID, msg, parse_mode='HTML')

        # Clean up JSON files
        original_filename = f"matches_{date_str}.json"
        if os.path.exists(original_filename):
            os.remove(original_filename)
        if os.path.exists(processed_filename):
            os.remove(processed_filename)
        print("Temporary files cleaned up.")
        
    except Exception as e:
        print(f"Error in send_daily_schedule: {e}")
        bot.send_message(CHANNEL_ID, f"⚠️ Error: {str(e)}")

def schedule_job():
    """Schedule the daily job at 7:00 AM GMT+7"""
    # Set the timezone to GMT+7 (Asia/Jakarta)
    gmt7 = pytz.timezone('Asia/Jakarta')
    
    # Schedule the job to run daily at 7:00 AM GMT+7
    schedule.every().day.at("07:00").do(send_daily_schedule).timezone = gmt7
    
    print("Scheduler started. Waiting for 7:00 AM GMT+7...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # For testing, you can uncomment the next line to send immediately
    send_daily_schedule()
    
    # For production, use the scheduler
    schedule_job()