import os
import json
import random
import requests
from datetime import datetime, timedelta

# ================= PROJECT DETAILS =================
PROJECT_NAME = "RadhaSocialSync"
AUTOMATION_NAME = "Daily Social Poster"

# ================= SECRETS (From GitHub ENV) =================
# ERROR FIX: Yahan variable ka naam RADHA_WEBHOOK_URL kar diya gaya hai
RADHA_WEBHOOK_URL = os.environ.get("RADHA_WEBHOOK_URL")
TELEGRAM_TOKEN_SUCCESS = os.environ.get("TELEGRAM_TOKEN_SUCCESS")
TELEGRAM_TOKEN_FAIL = os.environ.get("TELEGRAM_TOKEN_FAIL")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ================= DIRECTORIES =================
PHOTOS_DIR = "photos"
META_DIR = "meta"
HISTORY_FILE = "history.json"
# =================================================

def get_headers():
    """Real browser ki tarah behave karne ke liye User-Agent"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
    }

def upload_to_servers(file_path):
    """Uploads the local file to multiple fallback servers sequentially and returns the URL."""
    servers = [
        ("Catbox", lambda: requests.post("https://catbox.moe/user/api.php", data={'reqtype': 'fileupload'}, files={'fileToUpload': open(file_path, 'rb')}, headers=get_headers(), timeout=60)),
        ("Litterbox", lambda: requests.post("https://litterbox.catbox.moe/resources/internals/api.php", data={'reqtype': 'fileupload', 'time': '72h'}, files={'fileToUpload': open(file_path, 'rb')}, headers=get_headers(), timeout=60)),
        ("0x0.st", lambda: requests.post("https://0x0.st", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=60)),
        ("Uguu", lambda: requests.post("https://uguu.se/upload.php", files={'files[]': open(file_path, 'rb')}, headers=get_headers(), timeout=60)),
        ("qu.ax", lambda: requests.post("https://qu.ax/upload.php", files={'files[]': open(file_path, 'rb')}, headers=get_headers(), timeout=60)),
        ("Pixeldrain", lambda: requests.post("https://pixeldrain.com/api/file", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=60)),
        ("Fileditch", lambda: requests.post("https://up1.fileditch.com/upload.php", files={'files[]': open(file_path, 'rb')}, headers=get_headers(), timeout=60)),
        ("Oshi.at", lambda: requests.post("https://oshi.at", files={'f': open(file_path, 'rb')}, headers=get_headers(), timeout=60))
    ]

    for name, upload_func in servers:
        try:
            print(f"Trying to upload image to {name}...")
            response = upload_func()
            if response.status_code in [200, 201]:
                # Extract URL based on specific server response format
                if name == "Pixeldrain":
                    data = response.json()
                    if data.get("success"):
                        return f"https://pixeldrain.com/api/file/{data.get('id')}"
                elif name in ["Uguu", "qu.ax", "Fileditch"]:
                    data = response.json()
                    if data.get("success"):
                        return data["files"][0]["url"]
                elif name == "Oshi.at":
                    for line in response.text.split('\n'):
                        if "DL:" in line:
                            return line.split("DL:")[1].strip()
                    for line in response.text.split('\n'):
                        if line.startswith('http'):
                            return line.strip()
                else:
                    # Catbox, Litterbox, 0x0.st provide direct text URL
                    return response.text.strip()
            else:
                print(f"{name} returned status code {response.status_code}")
        except Exception as e:
            print(f"{name} failed: {e}")
            continue
            
    raise Exception("All fallback image servers failed to upload the image!")


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
        # ERROR FIX: Ensure checking the correctly renamed variable
        if not RADHA_WEBHOOK_URL:
            raise Exception("RADHA_WEBHOOK_URL GitHub Secret me set nahi hai!")

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
            raise Exception("No new photos available! Sabhi photos The `NameError: name 'RADHA_WEBHOOK_URL' is not defined` occurs because your script attempts to evaluate the variable `RADHA_WEBHOOK_URL` on line 137, but it hasn't been created or assigned a value earlier in the code. 

Because this is running in a GitHub Actions environment (`/home/runner/work/...`), this is typically caused by forgetting to load the environment variable at the top of your script.

To give you the exact, final code without removing any of your existing functions or features, **please paste the contents of your `main.py` file here.** 

In the meantime, the fix will involve adding the following near the top of your `main.py` file (after your imports):

```python
import os

# Fetch the webhook URL from environment variables
RADHA_WEBHOOK_URL = os.environ.get('RADHA_WEBHOOK_URL')
