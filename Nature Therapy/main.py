import os
import json
import random
import requests
from datetime import datetime

# Configurations
FOLDER_NAME = "Nature Therapy"
WEBHOOK_URL = os.getenv("WEBHOOK_NATURE_THERAPY") # Environment variable se webhook URL lega
SOCIAL_MEDIA_NAME = "Instagram/Pinterest" # Apne according change karein
AUTOMATION_NAME = "Nature Therapy Auto-Poster"

# File Paths (Folder ke andar)
script_dir = os.path.dirname(os.path.abspath(__file__))
if not os.path.basename(script_dir) == FOLDER_NAME:
    script_dir = os.path.join(script_dir, FOLDER_NAME)
    os.makedirs(script_dir, exist_ok=True)

TITLES_FILE = os.path.join(script_dir, "titles.txt")
HASHTAGS_FILE = os.path.join(script_dir, "hashtags.txt")
IMAGES_FILE = os.path.join(script_dir, "images.txt")
HISTORY_FILE = os.path.join(script_dir, "history.json")
TRACK_FILE = os.path.join(script_dir, "track.txt")

# Helper: Load Text Files
def load_list(filepath):
    if not os.path.exists(filepath):
        open(filepath, 'w').close()
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

# Helper: Load or Initialize JSON
def load_json(filepath):
    if not os.path.exists(filepath):
        return {"titles": {}, "hashtags": {}}
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return {"titles": {}, "hashtags": {}}

# Helper: Check 40 Days Logic
def is_eligible(item, history_dict):
    if item not in history_dict:
        return True
    last_used = datetime.strptime(history_dict[item], "%Y-%m-%d").date()
    days_diff = (datetime.now().date() - last_used).days
    return days_diff > 40

def main():
    if not WEBHOOK_URL:
        print("Error: WEBHOOK_NATURE_THERAPY environment variable missing.")
        return

    # 1. Load Data
    titles = load_list(TITLES_FILE)
    hashtags = load_list(HASHTAGS_FILE)
    images = load_list(IMAGES_FILE)
    history = load_json(HISTORY_FILE)
    tracked_urls = load_list(TRACK_FILE)

    if not titles or not hashtags or not images:
        print("Data files (titles.txt, hashtags.txt, images.txt) empty hain.")
        return

    # 2. Filter Eligible Items (40 days check & duplicate URL check)
    eligible_titles = [t for t in titles if is_eligible(t, history["titles"])]
    eligible_hashtags = [h for h in hashtags if is_eligible(h, history["hashtags"])]
    eligible_images = [img for img in images if img not in tracked_urls]

    if not eligible_titles or not eligible_hashtags or not eligible_images:
        print("Sufficient fresh data available nahi hai (40 days rule or URL duplicate).")
        return

    # 3. Select Randomly
    selected_title = random.choice(eligible_titles)
    selected_hashtag = random.choice(eligible_hashtags)
    selected_image = random.choice(eligible_images)

    # 4. Prepare Webhook Payload
    payload = {
        "title": selected_title,
        "hashtag": selected_hashtag,
        "image_url": selected_image,
        "automation_name": AUTOMATION_NAME,
        "social_media": SOCIAL_MEDIA_NAME
    }

    # 5. Send Webhook Request
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        
        # 6. Success: Update Tracking Files
        today_str = datetime.now().strftime("%Y-%m-%d")
        history["titles"][selected_title] = today_str
        history["hashtags"][selected_hashtag] = today_str
        
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4)
            
        with open(TRACK_FILE, 'a', encoding='utf-8') as f:
            f.write(selected_image + "\n")
            
        # Success Message Print/Log
        print(f"✅ SUCCESS: Post Sent Successfully!")
        print(f"Automation: {AUTOMATION_NAME} | Social Media: {SOCIAL_MEDIA_NAME}")
        print(f"Title: {selected_title}\nHashtag: {selected_hashtag}\nURL Tracked: {selected_image}")

    except Exception as e:
        print(f"❌ Failed to send webhook: {e}")

if __name__ == "__main__":
    main()
