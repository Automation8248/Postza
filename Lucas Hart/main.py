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

# Folder and File Paths
BASE_DIR = "Lucas Hart"
VIDEO_DIR = os.path.join(BASE_DIR, "video")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
CAPTION_FILE = os.path.join(BASE_DIR, "caption.txt")
QUOTES_FILE = os.path.join(BASE_DIR, "quotes.txt")
TITLE_FILE = os.path.join(BASE_DIR, "title.txt")
HASHTAG_FILE = os.path.join(BASE_DIR, "hastag.txt")

# Valid video extensions (ignores .txt, etc.)
VALID_VIDEO_EXT = ('.mp4', '.webm', '.avi', '.mov', '.mkv')

def send_telegram_alert(error_message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    text = f"🚨 *Automation Failed*\n*Name:* {AUTOMATION_NAME}\n*Error:* {error_message}"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
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

def cleanup_old_data(history_data, captions):
    """Deletes videos and removes captions from caption.txt if older than 30 days."""
    now = datetime.now()
    updated_captions = captions.copy()
    
    for entry in history_data:
        try:
            entry_date = datetime.fromisoformat(entry['timestamp'])
            if now - entry_date > timedelta(days=30):
                # 1. Delete Video File
                vid_path = os.path.join(VIDEO_DIR, entry['video'])
                if os.path.exists(vid_path):
                    os.remove(vid_path)
                    print(f"Cleaned up old video: {entry['video']}")
                
                # 2. Remove Caption from caption.txt list
                if entry['caption'] in updated_captions:
                    updated_captions.remove(entry['caption'])
                    print(f"Cleaned up old caption.")
        except Exception as e:
            print(f"Error processing cleanup for entry {entry}: {e}")
            
    return updated_captions

def main():
    try:
        if not os.path.exists(BASE_DIR):
            raise FileNotFoundError(f"Base folder '{BASE_DIR}' does not exist.")

        # 1. Load Data
        titles = read_file(TITLE_FILE)
        hashtags = read_file(HASHTAG_FILE)
        captions = read_file(CAPTION_FILE)
        history = load_history()
        
        # Extract used items to prevent repetition
        used_videos = [item['video'] for item in history]
        used_captions = [item['caption'] for item in history]

        # 2. Get un-used Videos
        all_videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(VALID_VIDEO_EXT)]
        available_videos = [v for v in all_videos if v not in used_videos]
        
        if not available_videos:
            raise ValueError("No new videos found! All videos have been used or folder is empty.")
            
        # 3. Get un-used Captions
        available_captions = [c for c in captions if c not in used_captions]
        if not available_captions:
            raise ValueError("No new captions found! Please add more to caption.txt.")

        # 4. Make Selections
        selected_video = random.choice(available_videos)
        selected_caption = random.choice(available_captions)
        selected_title = random.choice(titles)
        selected_hashtag = random.choice(hashtags)

        # 5. Send to Webhook
        video_raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{BRANCH}/{BASE_DIR}/video/{selected_video}".replace(" ", "%20")
        
        payload = {
            "title": selected_title,
            "hastag": selected_hashtag,
            "caption": selected_caption,
            "video_url": video_raw_url,
            "social_media_name": SOCIAL_MEDIA_NAME,
            "automation_name": AUTOMATION_NAME,
            "successful_message": "Successfully processed video and updated history."
        }
        
        print(f"Sending video: {selected_video} to Webhook...")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        response.raise_for_status()

        # 6. Update History & Files
        new_entry = {
            "video": selected_video,
            "caption": selected_caption,
            "timestamp": datetime.now().isoformat()
        }
        history.append(new_entry)
        
        # Write to quotes.txt
        with open(QUOTES_FILE, 'a', encoding='utf-8') as f:
            f.write(selected_caption + "\n")
            
        # 7. Run 30-Day Cleanup
        remaining_captions = cleanup_old_data(history, captions)
        
        # Overwrite caption.txt with cleaned up data
        with open(CAPTION_FILE, 'w', encoding='utf-8') as f:
            for cap in remaining_captions:
                f.write(cap + "\n")

        # Save updated JSON history
        save_history(history)
        print("Success! Webhook sent, history saved, and old files cleaned up.")

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        send_telegram_alert(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
