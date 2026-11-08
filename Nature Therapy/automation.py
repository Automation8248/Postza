import os
import random
import json
import requests
import traceback
from datetime import datetime, timedelta

# Environment Variables
WEBHOOK_URL = os.environ.get("NATURE_THERAPY_WEBHOOK")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_FAILD_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("FAILED_CHAT_ID")
THREAD_ID = "8"

# Directories and Files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_FILE = os.path.join(BASE_DIR, "images.txt")
TITLE_FILE = os.path.join(BASE_DIR, "title.txt")
HASHTAG_FILE = os.path.join(BASE_DIR, "hastag.txt")
TRACK_FILE = os.path.join(BASE_DIR, "track.json")

COOLING_DAYS = 90

def send_telegram_alert(error_msg):
    """Sends error alert to Telegram Thread"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Cannot send alert.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    message = (
        "🚨 *Automation Failed!*\n"
        "📁 *Repo Name:* postza\n"
        "👤 *Social media account:* Nature therapy\n"
        f"❌ *Error:* `{error_msg}`"
    )
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

def load_data(filepath):
    """Loads lines from a text file, ignoring empty lines."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Missing file: {filepath} - Please check if the file exists and the spelling/capitalization is exact.")
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_track_data():
    """Loads tracking JSON or creates a default structure."""
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"images": {}, "titles": {}, "hashtags": {}}

def save_track_data(data):
    """Saves tracking data back to JSON."""
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def filter_available(items, track_dict):
    """Filters out items that are currently in their 90-day cooling period."""
    available = []
    now = datetime.now()
    
    for item in items:
        if item in track_dict:
            last_used = datetime.strptime(track_dict[item], "%Y-%m-%d")
            # If 90 days haven't passed, skip this item
            if now < last_used + timedelta(days=COOLING_DAYS):
                continue
        available.append(item)
    return available

def is_valid_image_url(url):
    """Checks if the image URL is valid and returning a 200 OK status."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # stream=True ensures we only fetch headers, not download the full image, saving bandwidth/time
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print(f"Error checking URL {url}: {e}")
        return False

def main():
    try:
        # Load raw data
        all_images = load_data(IMAGES_FILE)
        all_titles = load_data(TITLE_FILE)
        all_hashtags = load_data(HASHTAG_FILE)
        
        # Load tracking data
        track_data = load_track_data()
        
        # Filter available items based on cooling period
        available_images = filter_available(all_images, track_data["images"])
        available_titles = filter_available(all_titles, track_data["titles"])
        available_hashtags = filter_available(all_hashtags, track_data["hashtags"])
        
        # Check if we have enough items
        if not available_images:
            raise ValueError("No available images found. All images are in cooling period.")
        if not available_titles:
            raise ValueError("No available titles found. All titles are in cooling period.")
        if not available_hashtags:
            raise ValueError("No available hashtags found. All hashtags are in cooling period.")
            
        # Select randomly for Title and Hashtag
        selected_title = random.choice(available_titles)
        selected_hashtag = random.choice(available_hashtags)
        
        # Select and Validate Image URL
        random.shuffle(available_images) # Shuffle list to pick randomly
        selected_image = None
        
        for img_url in available_images:
            print(f"Checking URL: {img_url}")
            if is_valid_image_url(img_url):
                selected_image = img_url
                print(f"Valid URL found: {selected_image}")
                break
            else:
                print(f"Invalid or broken URL skipped: {img_url}")
                
        # If loop finishes and no valid image is found
        if not selected_image:
            raise ValueError("No working image URLs found in the available list. All checked URLs returned errors.")
        
        # Send to Webhook
        if not WEBHOOK_URL:
            raise ValueError("NATURE_THERAPY_WEBHOOK secret is missing.")
            
        webhook_payload = {
            "title": selected_title,
            "hashtag": selected_hashtag,
            "image_url": selected_image
        }
        
        print("Sending to webhook...")
        response = requests.post(WEBHOOK_URL, json=webhook_payload)
        response.raise_for_status() # Raises exception if webhook fails (e.g., 404, 500)
        
        # Update tracking with today's date
        today_str = datetime.now().strftime("%Y-%m-%d")
        track_data["images"][selected_image] = today_str
        track_data["titles"][selected_title] = today_str
        track_data["hashtags"][selected_hashtag] = today_str
        
        # Clean up expired items from JSON to keep file size small
        for category in ["images", "titles", "hashtags"]:
            for key in list(track_data[category].keys()):
                last_used = datetime.strptime(track_data[category][key], "%Y-%m-%d")
                if datetime.now() >= last_used + timedelta(days=COOLING_DAYS):
                    del track_data[category][key]
                    
        # Save tracking data back so we know they are in cooldown now
        save_track_data(track_data)
        print("Successfully posted to webhook and updated track.json")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error occurred: {error_msg}")
        traceback.print_exc()
        send_telegram_alert(error_msg)
        raise e

if __name__ == "__main__":
    main()
