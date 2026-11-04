import os
import random
import requests
import sys
import json
from datetime import datetime, timedelta

# Environment Variables
WEBHOOK_URL = os.environ.get("LUCAS_WEBHOOK")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_FAILD_TOKEN")
CHAT_ID = os.environ.get("FAILED_CHAT_ID")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY")
BRANCH = "main"

AUTOMATION_NAME = "Lucas Webhook Video Automation"
SOCIAL_MEDIA_NAME = "Lucas Hart Accounts"
TELEGRAM_THREAD_ID = 2  # Added Thread ID for special Telegram topics

# Folder and File Paths
BASE_DIR = "Lucas Hart"
VIDEO_DIR = os.path.join(BASE_DIR, "video")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
CAPTION_FILE = os.path.join(BASE_DIR, "caption.txt")
QUOTES_FILE = os.path.join(BASE_DIR, "quotes.txt")
TITLE_FILE = os.path.join(BASE_DIR, "title.txt")
HASHTAG_FILE = os.path.join(BASE_DIR, "hastag.txt")

VALID_VIDEO_EXT = ('.mp4', '.webm', '.avi', '.mov', '.mkv')

def send_telegram_alert(error_message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    text = f"🚨 *Automation Failed*\n*Name:* {AUTOMATION_NAME}\n*Error:* {error_message}"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "message_thread_id": TELEGRAM_THREAD_ID # Sends to the specific thread
    }
    try:
        requests.post(url, json=payload)
    except:
        pass

def read_file(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_history(history_data):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, indent=4)

def main():
    try:
        if not os.path.exists(BASE_DIR):
            raise FileNotFoundError(f"Base folder '{BASE_DIR}' does not exist.")

        # 1. Load Data
        titles = read_file(TITLE_FILE)
        hashtags = read_file(HASHTAG_FILE)
        captions = read_file(CAPTION_FILE)
        history = load_history()
        
        now = datetime.now()
        
        # 2. Extract Data for Rules
        used_videos = [item['video'] for item in history]
        
        # Find hashtags used in the last 4 days
        recent_hashtags = []
        for entry in history:
            entry_date = datetime.fromisoformat(entry['timestamp'])
            if now - entry_date <= timedelta(days=4):
                if 'hashtag' in entry:
                    recent_hashtags.append(entry['hashtag'])

        # 3. Filter Valid Selections
        # Filter Videos
        all_videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(VALID_VIDEO_EXT)]
        available_videos = [v for v in all_videos if v not in used_videos]
        if not available_videos:
            raise ValueError("No new videos found! All videos have been used.")
            
        # Filter Captions
        if not captions:
            raise ValueError("caption.txt is empty! Please add more captions.")
            
        # Filter Hashtags (must not be used in last 4 days)
        available_hashtags = [h for h in hashtags if h not in recent_hashtags]
        if not available_hashtags:
            raise ValueError("No available hashtags! All hashtags have been used in the last 4 days.")

        # 4. Make Random Selections
        selected_video = random.choice(available_videos)
        selected_caption = random.choice(captions)
        selected_title = random.choice(titles)
        selected_hashtag = random.choice(available_hashtags)

        # 5. Format Custom Post Text for Webhook
        formatted_post_text = f"{selected_title}\n\n✨ {selected_caption}\n\n{selected_hashtag}"
        
        video_raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{BRANCH}/{BASE_DIR}/video/{selected_video}".replace(" ", "%20")
        
        # Webhook Payload
        payload = {
            "formatted_text": formatted_post_text,  # The exact formatted text you requested
            "title": selected_title,
            "hastag": selected_hashtag,
            "caption": selected_caption,
            "video_url": video_raw_url,
            "social_media_name": SOCIAL_MEDIA_NAME,
            "automation_name": AUTOMATION_NAME,
            "successful_message": "Successfully processed video with advanced logic."
        }
        
        print(f"Sending video: {selected_video} to Webhook...")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        response.raise_for_status()

        # 6. Post-Success File Operations
        
        # Remove selected caption from caption.txt immediately
        captions.remove(selected_caption)
        with open(CAPTION_FILE, 'w', encoding='utf-8') as f:
            for cap in captions:
                f.write(cap + "\n")

        # Append to active history
        new_entry = {
            "video": selected_video,
            "caption": selected_caption,
            "hashtag": selected_hashtag,
            "timestamp": now.isoformat()
        }
        history.append(new_entry)
        
        # 7. Perform 30-Day Cleanup
        valid_history = []
        for entry in history:
            entry_date = datetime.fromisoformat(entry['timestamp'])
            if now - entry_date > timedelta(days=30):
                # Delete video from folder after 30 days
                vid_path = os.path.join(VIDEO_DIR, entry['video'])
                if os.path.exists(vid_path):
                    os.remove(vid_path)
                    print(f"Deleted old video: {entry['video']}")
                # We skip adding this to valid_history, which removes it from tracking and quotes.txt
            else:
                valid_history.append(entry)

        # Update quotes.txt (Always matches exactly what is in valid 30-day history)
        with open(QUOTES_FILE, 'w', encoding='utf-8') as f:
            for entry in valid_history:
                f.write(entry['caption'] + "\n")

        # Save cleaned up history.json
        save_history(valid_history)
        
        print("Success! Webhook sent, used caption removed, history saved, and 30-day cleanup complete.")

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        send_telegram_alert(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
