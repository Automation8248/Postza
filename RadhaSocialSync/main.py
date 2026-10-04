import os
import json
import random
import requests
from datetime import datetime, timedelta

# ================= PROJECT DETAILS =================
PROJECT_NAME = "RadhaSocialSync"
AUTOMATION_NAME = "Daily Social Poster"

# ================= SECRETS (From GitHub ENV) =================
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
TELEGRAM_TOKEN_SUCCESS = os.environ.get("TELEGRAM_TOKEN_SUCCESS")
TELEGRAM_TOKEN_FAIL = os.environ.get("TELEGRAM_TOKEN_FAIL")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ================= DIRECTORIES =================
PHOTOS_DIR = "photos"
META_DIR = "meta"
HISTORY_FILE = "history.json"
# =================================================

def send_telegram_msg(token, chat_id, message):
    """Telegram par message bhejne ka function"""
    if not token or not chat_id:
        print("Telegram Token ya Chat ID missing hai!")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram notification failed: {e}")

def load_history():
    """90 days ki history load aur clean karna"""
    if not os.path.exists(HISTORY_FILE):
        return []
    
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        try:
            history = json.load(f)
        except json.JSONDecodeError:
            history = []

    cutoff_date = datetime.now() - timedelta(days=90)
    cleaned_history = []
    
    for item in history:
        item_date = datetime.strptime(item['date'], "%Y-%m-%d")
        if item_date >= cutoff_date:
            cleaned_history.append(item)
            
    return cleaned_history

def save_history(history):
    """History save karna"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)

def get_unused_item(items_list, used_items_set):
    """Aisa item nikalna jo history me use nahi hua ho"""
    random.shuffle(items_list)
    for item in items_list:
        if item.strip() and item.strip() not in used_items_set:
            return item.strip()
    return None

def read_file_lines(filename):
    """Text file se lines read karna"""
    filepath = os.path.join(META_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def main():
    try:
        if not WEBHOOK_URL:
            raise Exception("WEBHOOK_URL GitHub Secret me set nahi hai!")

        history = load_history()
        
        # History se used data ka set
        used_photos = {item.get('photo') for item in history}
        used_titles = {item.get('title') for item in history}
        used_captions = {item.get('caption') for item in history}

        # 1. Select Photo
        if not os.path.exists(PHOTOS_DIR):
            raise Exception(f"'{PHOTOS_DIR}' folder nahi mila!")
            
        all_photos = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        selected_photo = get_unused_item(all_photos, used_photos)
        
        if not selected_photo:
            raise Exception("No new photos available! Sabhi photos 90 days filter me hain.")

        # 2. Read Meta Files
        titles = read_file_lines('Title.txt')
        captions = read_file_lines('captions.txt')
        fb_hashtags = read_file_lines('facebook.txt')
        yt_hashtags = read_file_lines('youtube.txt') # Youtube hashtags file
        insta_hashtags = read_file_lines('insta.txt')
        universal_hashtags = read_file_lines('universal.txt')

        # 3. Select Unused Title and Caption
        selected_title = get_unused_item(titles, used_titles)
        selected_caption = get_unused_item(captions, used_captions)

        if not selected_title:
            raise Exception("No new titles available in Title.txt!")
        if not selected_caption:
            raise Exception("No new captions available in captions.txt!")

        # 4. Select Hashtags (Random pick)
        fb_hash = random.choice(fb_hashtags) if fb_hashtags else ""
        yt_hash = random.choice(yt_hashtags) if yt_hashtags else ""
        insta_hash = random.choice(insta_hashtags) if insta_hashtags else ""
        univ_hash = random.choice(universal_hashtags) if universal_hashtags else ""

        # 5. Prepare Webhook Payload
        photo_path = os.path.join(PHOTOS_DIR, selected_photo)
        
        payload_data = {
            "title": selected_title,
            "caption": selected_caption,
            "fb_hashtags": fb_hash,
            "yt_hashtags": yt_hash,
            "insta_hashtags": insta_hash,
            "universal_hashtags": univ_hash
        }
        
        # 6. Post to Webhook
        with open(photo_path, 'rb') as img_file:
            files = {'image': (selected_photo, img_file, 'image/jpeg')}
            response = requests.post(WEBHOOK_URL, data=payload_data, files=files)
            
            if response.status_code in [200, 201, 204]:
                # SUCCESS
                today_date = datetime.now().strftime("%Y-%m-%d")
                history.append({
                    "photo": selected_photo,
                    "title": selected_title,
                    "caption": selected_caption,
                    "date": today_date
                })
                save_history(history)
                
                success_msg = (
                    f"✅ <b>Success!</b>\n\n"
                    f"<b>Project:</b> {PROJECT_NAME}\n"
                    f"<b>Automation:</b> {AUTOMATION_NAME}\n"
                    f"<b>Photo:</b> {selected_photo}\n"
                    f"<b>Status:</b> Successfully posted to Webhook."
                )
                send_telegram_msg(TELEGRAM_TOKEN_SUCCESS, TELEGRAM_CHAT_ID, success_msg)
                print("Successful post! History updated.")
                
            else:
                raise Exception(f"Webhook response failed! Status Code: {response.status_code}, Msg: {response.text}")

    except Exception as e:
        # FAILED
        error_msg = (
            f"❌ <b>Automation Failed!</b>\n\n"
            f"<b>Project:</b> {PROJECT_NAME}\n"
            f"<b>Automation:</b> {AUTOMATION_NAME}\n"
            f"<b>Error Details:</b> {str(e)}"
        )
        send_telegram_msg(TELEGRAM_TOKEN_FAIL, TELEGRAM_CHAT_ID, error_msg)
        print(f"Error occurred: {str(e)}")
        # Raise takki GitHub Action red cross mark (fail status) show kare
        raise e 

if __name__ == "__main__":
    main()
