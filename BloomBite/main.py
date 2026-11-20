import os
import json
import random
import requests
import traceback
import urllib.parse
from datetime import datetime, timedelta

# ======== CONFIGURATION ========
WEBHOOK_URL = os.environ.get("BLOOMBITE_WEBHOOK")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_FAILD_TOKEN")
CHAT_ID = os.environ.get("FAILED_CHAT_ID")
THREAD_ID = 8
COOLDOWN_DAYS = 120

# Directory and File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACK_FILE = os.path.join(BASE_DIR, 'track.json')
TITLE_FILE = os.path.join(BASE_DIR, 'title.txt')
HASHTAG_FILE = os.path.join(BASE_DIR, 'hastag.txt')

def send_telegram_alert(error_msg):
    """Sends a failure alert to the specified Telegram thread."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram credentials missing. Skipping alert.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    text = (
        f"🚨 *Automation Failed*\n"
        f"👤 *Social Media:* BloomBite\n"
        f"📂 *Repo Name:* Postza\n"
        f"📁 *Folder Name:* BloomBite\n\n"
        f"⚠️ *Error Message:*\n`{error_msg}`"
    )
    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram alert failed to send: {e}")

def load_tracking():
    """Loads track.json data or initializes if empty."""
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"titles": {}, "hashtags": {}, "images": {}}
    return {"titles": {}, "hashtags": {}, "images": {}}

def save_tracking(data):
    """Saves updated data to track.json."""
    with open(TRACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def is_cooled_down(item, tracking_dict):
    """Checks if an item is completely new or has passed the 120-day cooldown."""
    if item not in tracking_dict:
        return True
    last_used = datetime.fromisoformat(tracking_dict[item])
    if datetime.now() - last_used >= timedelta(days=COOLDOWN_DAYS):
        return True
    return False

def read_file_lines(filepath):
    """Reads lines from a text file, filtering out blanks."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Missing required file: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def get_random_image_link(tracking_data):
    """Fetches a random image link from a randomly selected folder in the Codvix repo."""
    repo_api_url = "https://api.github.com/repos/Automation8248/Codvix/contents/Pixhub/Social%20post/Flowers"
    
    response = requests.get(repo_api_url)
    if response.status_code != 200:
        raise Exception(f"Failed to list GitHub folders. API Response: {response.text}")
    
    folders = [item['name'] for item in response.json() if item['type'] == 'dir']
    if not folders:
        raise Exception("No folders found in the Flowers directory.")
    
    # Shuffle folders to randomly search for an available link
    random.shuffle(folders)
    
    for folder in folders:
        # Encode folder name for URL (handles spaces)
        folder_encoded = urllib.parse.quote(folder)
        link_url = f"https://raw.githubusercontent.com/Automation8248/Codvix/main/Pixhub/Social%20post/Flowers/{folder_encoded}/link.txt"
        
        link_resp = requests.get(link_url)
        if link_resp.status_code == 200:
            links = [line.strip() for line in link_resp.text.split('\n') if line.strip()]
            valid_links = [l for l in links if is_cooled_down(l, tracking_data['images'])]
            
            if valid_links:
                return random.choice(valid_links), folder

    raise Exception("No available image links found across all folders (all are currently in 120-day cooldown).")

def main():
    try:
        # 1. Load Data
        tracking = load_tracking()
        titles = read_file_lines(TITLE_FILE)
        hashtags = read_file_lines(HASHTAG_FILE)

        # 2. Filter Valid Items (Passed 120-day Cooldown)
        valid_titles = [t for t in titles if is_cooled_down(t, tracking['titles'])]
        valid_hashtags = [h for h in hashtags if is_cooled_down(h, tracking['hashtags'])]

        if not valid_titles:
            raise Exception("No titles available. All are in 120-day cooldown.")
        if not valid_hashtags:
            raise Exception("No hashtags available. All are in 120-day cooldown.")

        # 3. Select Random Items
        selected_title = random.choice(valid_titles)
        selected_hashtag = random.choice(valid_hashtags)
        selected_image, selected_folder = get_random_image_link(tracking)

        # 4. Post to Webhook
        if not WEBHOOK_URL:
            raise ValueError("BLOOMBITE_WEBHOOK URL is missing in Secrets.")

        payload = {
            "title": selected_title,
            "hashtag": selected_hashtag,
            "image_link": selected_image,
            "folder": selected_folder
        }

        wh_response = requests.post(WEBHOOK_URL, json=payload)
        if wh_response.status_code not in (200, 201, 204):
            raise Exception(f"Webhook failed! Status: {wh_response.status_code} - {wh_response.text}")

        # 5. Update Tracking & Reset Cooldown
        now_str = datetime.now().isoformat()
        tracking['titles'][selected_title] = now_str
        tracking['hashtags'][selected_hashtag] = now_str
        tracking['images'][selected_image] = now_str

        save_tracking(tracking)
        print(f"✅ Successfully posted and tracked! (Image from folder: {selected_folder})")

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {traceback.format_exc()}")
        send_telegram_alert(error_msg)
        raise  # Fails the GitHub Action deliberately after sending Telegram message

if __name__ == "__main__":
    main()
