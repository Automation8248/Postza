import os
import random
import requests
import sys
import json
from datetime import datetime, timedelta

# Environment Variables (Added .strip() to fix %0A spacing issues)
WEBHOOK_URL = os.environ.get("LUCAS_WEBHOOK", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_FAILD_TOKEN", "").strip()
CHAT_ID = os.environ.get("FAILED_CHAT_ID", "").strip()

# Hardcoded Repo Details 
GITHUB_REPO = "Automation8248/Postza" 
BRANCH = "main"

AUTOMATION_NAME = "postza"
SOCIAL_MEDIA_NAME = "Lucas Hart"
TELEGRAM_THREAD_ID = 8

# Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "video")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
CAPTION_FILE = os.path.join(BASE_DIR, "caption.txt")
QUOTES_FILE = os.path.join(BASE_DIR, "quotes.txt")
TITLE_FILE = os.path.join(BASE_DIR, "title.txt")
HASHTAG_FILE = os.path.join(BASE_DIR, "hastag.txt")

# STRICT FILTER: Only these extensions will be picked up and deleted. (Added .webp)
VALID_VIDEO_EXT = ('.mp4', '.webm', '.webp', '.avi', '.mov', '.mkv')

def send_telegram_alert(error_message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    text = f"🚨 *Automation Failed*\n*Repo Name:* {AUTOMATION_NAME}\n*Social Media:* {SOCIAL_MEDIA_NAME}\n*Error Details:* {error_message}"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "message_thread_id": TELEGRAM_THREAD_ID
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
        if not os.path.exists(VIDEO_DIR):
            raise FileNotFoundError("The 'video' folder does not exist inside Lucas Hart folder.")

        titles = read_file(TITLE_FILE)
        hashtags = read_file(HASHTAG_FILE)
        captions = read_file(CAPTION_FILE)
        history = load_history()
        now = datetime.now()
        
        used_videos = [item['video'] for item in history]
        
        # 4-Day Hashtag Rule
        recent_hashtags = []
        for entry in history:
            entry_date = datetime.fromisoformat(entry['timestamp'])
            if now - entry_date <= timedelta(days=4) and 'hashtag' in entry:
                recent_hashtags.append(entry['hashtag'])

        # Filters - Picks UP ONLY files ending with valid extensions
        all_videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(VALID_VIDEO_EXT)]
        available_videos = [v for v in all_videos if v not in used_videos]
        
        if not available_videos:
            raise ValueError("No new videos found in 'video' folder! (txt and other files are ignored)")
            
        if not captions:
            raise ValueError("caption.txt is empty!")
            
        available_hashtags = [h for h in hashtags if h not in recent_hashtags]
        if not available_hashtags:
            raise ValueError("All hashtags have been used in the last 4 days.")
            
        if not titles:
            raise ValueError("title.txt is missing or empty.")

        # Selections
        selected_video = random.choice(available_videos)
        selected_caption = random.choice(captions)
        selected_title = random.choice(titles)
        selected_hashtag = random.choice(available_hashtags)

        formatted_post_text = f"{selected_title}\n\n✨ {selected_caption}\n\n{selected_hashtag}"
        
        # Raw GitHub URL
        video_raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{BRANCH}/Lucas%20Hart/video/{selected_video}".replace(" ", "%20")
        
        payload = {
            "formatted_text": formatted_post_text,
            "title": selected_title,
            "hastag": selected_hashtag,
            "caption": selected_caption,
            "video_url": video_raw_url,
            "social_media_name": SOCIAL_MEDIA_NAME,
            "automation_name": AUTOMATION_NAME,
            "successful_message": "Video successfully processed."
        }
        
        print(f"Sending video: {selected_video} to Webhook...")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        response.raise_for_status()

        # Update caption.txt
        captions.remove(selected_caption)
        with open(CAPTION_FILE, 'w', encoding='utf-8') as f:
            for cap in captions:
                f.write(cap + "\n")

        # Update History
        new_entry = {
            "video": selected_video,
            "caption": selected_caption,
            "hashtag": selected_hashtag,
            "timestamp": now.isoformat()
        }
        history.append(new_entry)
        
        # 30-Day Cleanup (STRICT DELETE)
        valid_history = []
        for entry in history:
            entry_date = datetime.fromisoformat(entry['timestamp'])
            if now - entry_date > timedelta(days=30):
                vid_path = os.path.join(VIDEO_DIR, entry['video'])
                
                # Double Safety: Check if file exists AND ends with valid video extension before deleting
                if os.path.exists(vid_path) and entry['video'].lower().endswith(VALID_VIDEO_EXT):
                    os.remove(vid_path)
                    print(f"Deleted 30-day old video: {entry['video']}")
                elif os.path.exists(vid_path):
                    print(f"Skipped deleting {entry['video']} as it is not a valid video extension.")
            else:
                valid_history.append(entry)

        with open(QUOTES_FILE, 'w', encoding='utf-8') as f:
            for entry in valid_history:
                f.write(entry['caption'] + "\n")

        save_history(valid_history)
        print("Success! Webhook sent, used caption removed, history saved, and cleanup complete.")

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        send_telegram_alert(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
