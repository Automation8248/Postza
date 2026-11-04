import os
import json
import random
import requests
from datetime import datetime, timedelta

# Configurations
FOLDER_NAME = "Kavlio"
REPO_NAME = "Postza"
WEBHOOK_URL = os.environ.get("KAVLIO_WEBHOOK")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_FAILD_TOKEN")
CHAT_ID = os.environ.get("FAILED_CHAT_ID")
THREAD_ID = "8"
COOLING_DAYS = 90

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TITLE_FILE = os.path.join(BASE_DIR, "title.txt")
DESC_FILE = os.path.join(BASE_DIR, "discription.txt")
URL_FILE = os.path.join(BASE_DIR, "post.txt")
EBOOK_FILE = os.path.join(BASE_DIR, "ebook.txt") # New Ebook file
TRACK_FILE = os.path.join(BASE_DIR, "track.json")

def send_telegram_error(error_msg):
    """Sends an error message to a specific Telegram thread if the script fails."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram credentials missing, skipping alert.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    text = f"🚨 *Automation Failed*\n\n*Repo:* {REPO_NAME}\n*Folder:* {FOLDER_NAME}\n*Error:* \n`{error_msg}`"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "message_thread_id": THREAD_ID
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

def load_lines(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_track_data():
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {"titles": {}, "descriptions": {}, "urls": {}}

def save_track_data(data):
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def filter_available_items(items, category_track, now):
    available = []
    for item in items:
        if item in category_track:
            last_used = datetime.fromisoformat(category_track[item])
            if now - last_used < timedelta(days=COOLING_DAYS):
                continue # Still in 90-day cooling period
        available.append(item)
    return available

def main():
    try:
        titles = load_lines(TITLE_FILE)
        descriptions = load_lines(DESC_FILE)
        urls = load_lines(URL_FILE)
        ebooks = load_lines(EBOOK_FILE) # Load ebooks
        
        if not titles or not descriptions or not urls:
            raise ValueError("title.txt, discription.txt, or post.txt file is empty or missing.")
            
        if not ebooks:
            raise ValueError("ebook.txt file is empty or missing.")

        track_data = load_track_data()
        now = datetime.now()

        # Clean up old tracking data (older than 90 days) to keep track.json small
        for category in ["titles", "descriptions", "urls"]:
            if category not in track_data:
                track_data[category] = {}
            keys_to_delete = [k for k, v in track_data[category].items() if now - datetime.fromisoformat(v) >= timedelta(days=COOLING_DAYS)]
            for k in keys_to_delete:
                del track_data[category][k]

        available_titles = filter_available_items(titles, track_data["titles"], now)
        available_descs = filter_available_items(descriptions, track_data["descriptions"], now)
        available_urls = filter_available_items(urls, track_data["urls"], now)

        if not available_titles:
            raise Exception("No available titles. All titles are in 90-day cooling.")
        if not available_descs:
            raise Exception("No available descriptions. All descriptions are in 90-day cooling.")
        if not available_urls:
            raise Exception("No available URLs. All URLs are in 90-day cooling.")

        # Pick randomly from available items (with cooling)
        selected_title = random.choice(available_titles)
        selected_desc = random.choice(available_descs)
        selected_url = random.choice(available_urls)
        
        # Pick randomly from ebook items (NO COOLING - picks from full list every time)
        selected_ebook = random.choice(ebooks)

        # Webhook Payload
        if not WEBHOOK_URL:
            raise ValueError("KAVLIO_WEBHOOK environment variable is not set.")
        
        payload = {
            "title": selected_title,
            "description": selected_desc,
            "url": selected_url,
            "ebook": selected_ebook
        }
        
        # Send to webhook
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()

        # Update tracking JSON with current time (restarts the 90 days)
        # Note: We do NOT track selected_ebook here so it never gets a cooling period
        iso_now = now.isoformat()
        track_data["titles"][selected_title] = iso_now
        track_data["descriptions"][selected_desc] = iso_now
        track_data["urls"][selected_url] = iso_now

        save_track_data(track_data)
        print(f"✅ Successfully posted to webhook! Selected Ebook URL: {selected_ebook}")

    except Exception as e:
        error_message = str(e)
        print(f"Error: {error_message}")
        send_telegram_error(error_message)
        raise # Fail the GitHub action run

if __name__ == "__main__":
    main()
