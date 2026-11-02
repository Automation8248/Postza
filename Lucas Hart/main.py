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

def get_available_hashtags(history_data, all_hashtags):
    """Filters out hashtags used in the last 4 days."""
    now = datetime.now()
    recently_used = []
    
    for entry in history_data:
        if 'hashtag' in entry:
            try:
                entry_date = datetime.fromisoformat(entry['timestamp'])
                if now - entry_date <= timedelta(days=4):
                    recently_used.append(entry['hashtag'])
            except Exception:
                pass
                
    available = [h for h in all_hashtags if h not in recently_used]
    if not available:
        print("Warning: All hashtags used in last 4 days. Using random from all.")
        return all_hashtags
    return available

def cleanup_old_data(history_data, captions):
    """Deletes videos & removes captions from file if older than 30 days."""
    now = datetime.now()
    updated_captions = captions.copy()
    cleaned_history = []
    
    for entry in history_data:
        try:
            entry_date = datetime.fromisoformat(entry['timestamp'])
            if now - entry_date > timedelta(days=30):
                # 1. Delete Video File
                vid_path = os.path.join(VIDEO_DIR, entry['video'])
                if os.path.exists(vid_path):
                    os.remove(vid_path)
                    print(f"Cleaned up 30-day old video: {entry['video']}")
                
                # 2. Remove Caption from caption.txt
                if entry['caption'] in updated_captions:
                    updated_captions.remove(entry['caption'])
                    print(f"Cleaned up 30-day old caption.")
            else:
                # Keep in history if it's less than 30 days old
                cleaned_history.append(entry)
        except Exception as e:
            cleaned_history.append(entry)
            
    return updated_captions, cleaned_history

def main():
    try:
        if not os.path.exists(BASE_DIR):
            raise FileNotFoundError(f"Base folder '{BASE_DIR}' does not exist.")

        # 1. Load Data
        titles = read_file(TITLE_FILE)
        hashtags = read_file(HASHTAG_FILE)
        captions = read_file(CAPTION_FILE)
        history = load_history()
        
        used_videos = [item['video'] for item in history]
        used_captions = [item['caption'] for item in history]

        # 2. Find Available Videos
        all_videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(VALID_VIDEO_EXT)]
        available_videos = [v for v in all_videos if v not in used_videos]
        
        if not available_videos:
            raise ValueError("No new videos found in folder!")
            
        # 3. Find Available Captions
        available_captions = [c for c in captions if c not in used_captions]
        if not available_captions:
            raise ValueError("No new captions found in caption.txt!")

        # 4. Make Selections
        selected_video = random.choice(available_videos)
        selected_caption = random.choice(available_captions)
        selected_title = random.choice(titles)
        selected_hashtag = random.choice(get_available_hashtags(history, hashtags))

        # 5. Prepare Webhook Payload Formatting
        video_raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{BRANCH}/{BASE_DIR}/video/{selected_video}".replace(" ", "%20")
        
        # User requested format: {clean_title} \n\n✨ {caption}\n\n { hastag}
        formatted_message = f"{selected_title}\n\n✨ {selected_caption}\n\n{selected_hashtag}"
        
        payload = {
            "title": selected_title,
            "hastag": selected_hashtag,
            "caption": selected_caption,
            "formatted_text": formatted_message, # Use this key in webhook to get the final text
            "video_url": video_raw_url,
            "social_media_name": SOCIAL_MEDIA_NAME,
            "automation_name": AUTOMATION_NAME,
            "successful_message": "Successfully processed video and updated history."
        }
        
        print("Sending to Webhook...")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        response.raise_for_status()

        # 6. Update History (Video, Caption, Hashtag)
        new_entry = {
            "video": selected_video,
            "caption": selected_caption,
            "hashtag": selected_hashtag,
            "timestamp": datetime.now().isoformat()
        }
        history.append(new_entry)
        
        # Save caption to quotes.txt
        with open(QUOTES_FILE, 'a', encoding='utf-8') as f:
            f.write(selected_caption + "\n")
            
        # 7. Run 30-Day Cleanup
        remaining_captions, updated_history = cleanup_old_data(history, captions)
        
        # Overwrite caption.txt with remaining captions
        with open(CAPTION_FILE, 'w', encoding='utf-8') as f:
            for cap in remaining_captions:
                f.write(cap + "\n")

        # Save updated history (which automatically removes 30-day old items)
        save_history(updated_history)
        print("Success! Webhook sent, history saved, and older data cleaned up.")

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        send_telegram_alert(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
