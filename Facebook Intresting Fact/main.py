import os
import json
import random
import requests
import traceback
from datetime import datetime, timedelta

# Secrets from Environment Variables
WEBHOOK_URL = os.getenv("FACEBOOK_INTRESTING_FACT_WEBHOOK")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_FAILD_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("FAILED_CHAT_ID")

# Paths setup
BASE_FOLDER = "Facebook Intresting Fact"
VIDEO_FOLDER = os.path.join(BASE_FOLDER, "Videos")
TRACK_FILE = os.path.join(BASE_FOLDER, "track.json")
TITLE_FILE = os.path.join(BASE_FOLDER, "title.txt")
HASHTAG_FILE = os.path.join(BASE_FOLDER, "hastag.txt")

COOLING_DAYS = 60
VALID_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

def send_telegram_alert(error_message):
    """Failure hone par Telegram thread 8 me alert bhejta hai."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing, alert send nahi hua.")
        return

    text = (
        f"🚨 **Automation Failed**\n\n"
        f"**Automation Name:** Facebook Interesting Fact\n"
        f"**Social Media:** Facebook\n"
        f"**Repository:** Postza\n\n"
        f"**Error Details:**\n`{error_message}`"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": 8,  # Apki thread ID
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Telegram alert failed: {response.text}")
    except Exception as e:
        print(f"Telegram request failed: {e}")

def load_tracking_data():
    if not os.path.exists(TRACK_FILE):
        return {"titles": {}, "hashtags": {}}
    
    with open(TRACK_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"titles": {}, "hashtags": {}}
            
    now = datetime.now()
    cleaned_data = {"titles": {}, "hashtags": {}}
    
    for category in ["titles", "hashtags"]:
        if category in data:
            for item, timestamp_str in data[category].items():
                item_date = datetime.fromisoformat(timestamp_str)
                if now - item_date < timedelta(days=COOLING_DAYS):
                    cleaned_data[category][item] = timestamp_str
                    
    return cleaned_data

def save_tracking_data(data):
    with open(TRACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_available_items(filepath, cooling_dict):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Missing file: {filepath}")
        
    with open(filepath, 'r', encoding='utf-8') as f:
        items = [line.strip() for line in f.readlines() if line.strip()]
        
    return [item for item in items if item not in cooling_dict]

def get_random_video():
    if not os.path.exists(VIDEO_FOLDER):
        raise FileNotFoundError(f"Missing folder: {VIDEO_FOLDER}. Please create it and add videos.")

    files = os.listdir(VIDEO_FOLDER)
    videos = [f for f in files if os.path.splitext(f)[1].lower() in VALID_VIDEO_EXTENSIONS]
    
    if not videos:
        raise ValueError(f"'{VIDEO_FOLDER}' me koi valid video (.mp4, etc.) nahi mili.")
        
    return os.path.join(VIDEO_FOLDER, random.choice(videos))

def post_to_webhook(video_path, title, hashtag):
    if not WEBHOOK_URL:
        raise ValueError("FACEBOOK_INTRESTING_FACT_WEBHOOK environment variable set nahi hai.")

    message_content = f"{title}\n\n{hashtag}"
    payload = {"content": message_content}
    
    with open(video_path, 'rb') as f:
        files = {'file': (os.path.basename(video_path), f, 'application/octet-stream')}
        response = requests.post(WEBHOOK_URL, data=payload, files=files)
        
        if response.status_code not in [200, 204]:
            raise Exception(f"Webhook failed with status {response.status_code}: {response.text}")

def main():
    try:
        tracking_data = load_tracking_data()
        
        available_titles = get_available_items(TITLE_FILE, tracking_data["titles"])
        available_hashtags = get_available_items(HASHTAG_FILE, tracking_data["hashtags"])
        
        if not available_titles:
            raise ValueError("Koi title nahi bacha (Sab 60-day cooling me hain).")
        if not available_hashtags:
            raise ValueError("Koi hashtag nahi bacha (Sab 60-day cooling me hain).")

        selected_title = random.choice(available_titles)
        selected_hashtag = random.choice(available_hashtags)
        selected_video_path = get_random_video()
        
        print(f"Posting Video: {selected_video_path}")
        post_to_webhook(selected_video_path, selected_title, selected_hashtag)
        
        # Success hone ke baad track save aur video delete karein
        current_time_str = datetime.now().isoformat()
        tracking_data["titles"][selected_title] = current_time_str
        tracking_data["hashtags"][selected_hashtag] = current_time_str
        save_tracking_data(tracking_data)
        
        os.remove(selected_video_path)
        print(f"Successfully posted aur video delete ho gayi: {selected_video_path}")

    except Exception as e:
        error_msg = str(e)
        full_trace = traceback.format_exc()
        print(f"Error aagaya:\n{full_trace}")
        
        # Telegram par sirf clean error message bhejenge (ya chahein toh trace bhi bhej sakte hain)
        send_telegram_alert(error_msg)
        raise e  # GitHub Action ko fail mark karne ke liye raise karna zaroori hai

if __name__ == "__main__":
    main()
