import os
import random
import requests
import traceback
import json
import base64
from datetime import datetime

# === CONFIGURATION ===
GITHUB_REPO = "Automation8248/Codvix"
BASE_PATH = "Pixhub/Social post/Birds"
TRACK_FILE_PATH = f"{BASE_PATH}/track.json"

WEBHOOK_URL = os.environ.get("WINGS_OF_WONDER")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_SUCCESS_TOKEN = os.environ.get("TELEGRAM_TOKEN_SUCCESS")
TELEGRAM_FAIL_TOKEN = os.environ.get("TELEGRAM_TOKEN_FAIL")
GITHUB_TOKEN = os.environ.get("GH_TOKEN") # Used ONLY for saving track.json

AUTOMATION_NAME = "Birds Image Auto-Poster"
SOCIAL_PAGE_NAME = "Wings of Wonder"

# Constraints (in days)
IMAGE_COOLDOWN_DAYS = 547  # ~18 Months
TEXT_COOLDOWN_DAYS = 30    # 30 Days

def get_headers():
    return {"User-Agent": "Mozilla/5.0"}

def send_telegram(token, message):
    if not token or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def get_github_contents(path):
    """Public read - No token required for public repos"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json()

def fetch_raw_text(download_url):
    """Public read direct file"""
    res = requests.get(download_url, headers=get_headers())
    res.raise_for_status()
    return res.text.strip()

def get_random_line(text_data):
    """Helper function to pick one random line from a text file"""
    lines = [line.strip() for line in text_data.split('\n') if line.strip()]
    return random.choice(lines) if lines else ""

# ================= TRACKING LOGIC =================
def load_track_data():
    """Fetch track.json from GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TRACK_FILE_PATH}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    res = requests.get(url, headers=headers)
    
    default_data = {"last_folder_index": -1, "images": {}, "titles": {}, "hashtags": {}}
    
    if res.status_code == 200:
        data = res.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        try:
            parsed_data = json.loads(content)
            for k in default_data:
                if k not in parsed_data:
                    parsed_data[k] = default_data[k]
            return parsed_data, data['sha']
        except json.JSONDecodeError:
            return default_data, data['sha']
            
    return default_data, None

def save_track_data(track_data, sha):
    """Save updated track.json back to GitHub - Token REQUIRED here"""
    if not GITHUB_TOKEN:
        print("Warning: GH_TOKEN not found! Cannot save track.json.")
        return
        
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TRACK_FILE_PATH}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    encoded_content = base64.b64encode(json.dumps(track_data, indent=4).encode('utf-8')).decode('utf-8')
    payload = {
        "message": "Update track.json (Auto-Poster) [skip ci]",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha
        
    res = requests.put(url, headers=headers, json=payload)
    res.raise_for_status()

def is_cooled_down(item, category, track_data, days):
    if item not in track_data[category]:
        return True
    last_used = datetime.fromisoformat(track_data[category][item])
    if (datetime.now() - last_used).days < days:
        return False
    return True
# ==================================================

def extract_url_from_response(server_name, response):
    if server_name in ["Catbox", "Litterbox", "0x0.st", "Transfer.sh", "Temp.sh", "Bashupload"]:
        return response.text.strip()
    elif server_name in ["Uguu.se", "Pomf.lain.la"]:
        return response.json()['files'][0]['url']
    elif server_name == "Tmpfiles.org":
        url = response.json()['data']['url']
        return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    elif server_name == "File.io":
        return response.json()['link']
    return response.text.strip()

def upload_image_fallback(file_path):
    filename = os.path.basename(file_path)
    servers = [
        ("Catbox", lambda: requests.post("https://catbox.moe/user/api.php", data={'reqtype': 'fileupload'}, files={'fileToUpload': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("Litterbox", lambda: requests.post("https://litterbox.catbox.moe/resources/internals/api.php", data={'reqtype': 'fileupload', 'time': '72h'}, files={'fileToUpload': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("0x0.st", lambda: requests.post("https://0x0.st", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("Transfer.sh", lambda: requests.put(f"https://transfer.sh/{filename}", data=open(file_path, 'rb'), headers=get_headers(), timeout=30)),
        ("Uguu.se", lambda: requests.post("https://uguu.se/upload.php", files={'files[]': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("Tmpfiles.org", lambda: requests.post("https://tmpfiles.org/api/v1/upload", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("Pomf.lain.la", lambda: requests.post("https://pomf.lain.la/upload.php", files={'files[]': open(file_path, 'rb')}, headers=get_headers(), timeout=30)),
        ("Temp.sh", lambda: requests.put(f"https://temp.sh/{filename}", data=open(file_path, 'rb'), headers=get_headers(), timeout=30)),
        ("Bashupload", lambda: requests.put(f"https://bashupload.com/{filename}", data=open(file_path, 'rb'), headers=get_headers(), timeout=30)),
        ("File.io", lambda: requests.post("https://file.io", files={'file': open(file_path, 'rb')}, headers=get_headers(), timeout=30))
    ]

    for name, upload_func in servers:
        try:
            print(f"Trying upload to {name}...")
            res = upload_func()
            if res.status_code in [200, 201]:
                return extract_url_from_response(name, res)
            else:
                print(f"{name} failed with status {res.status_code}")
        except Exception as e:
            print(f"{name} failed: {e}")
            continue
    raise Exception("All fallback servers failed.")

def main():
    temp_image_path = "temp_image.jpg"
    try:
        track_data, track_sha = load_track_data()
        last_index = track_data.get('last_folder_index', -1)

        contents = get_github_contents(BASE_PATH)
        folders = sorted([item for item in contents if item['type'] == 'dir'], key=lambda x: x['name'])
        total_folders = len(folders)
        
        if total_folders == 0:
            raise Exception("No folders found in the Birds directory.")

        selected_folder = None
        selected_image_link = None
        final_title = "Beautiful Bird!"
        final_hashtags = "#nature #birds"
        current_index = 0

        # Loop sequentially through folders
        for i in range(total_folders):
            current_index = (last_index + 1 + i) % total_folders
            folder = folders[current_index]
            folder_path = folder['path']
            print(f"Checking Folder (Index {current_index}): {folder['name']}")

            # Fetch Text Metadata from WingWonder Folder
            metadata_path = f"{folder_path}/WingWonder"
            
            t_title = "Beautiful Bird!"
            t_insta = ""
            t_fb = ""
            t_yt = ""

            try:
                metadata_contents = get_github_contents(metadata_path)
                for item in metadata_contents:
                    name = item['name'].lower()
                    if name == 'title.txt':
                        raw = fetch_raw_text(item['download_url'])
                        t_title = get_random_line(raw) or t_title
                    elif name == 'insta.txt':
                        raw = fetch_raw_text(item['download_url'])
                        t_insta = get_random_line(raw)
                    elif name == 'facebook.txt':
                        raw = fetch_raw_text(item['download_url'])
                        t_fb = get_random_line(raw)
                    elif name == 'youtube.txt':
                        raw = fetch_raw_text(item['download_url'])
                        t_yt = get_random_line(raw)
                        
                # Combine all selected hashtags
                tags_list = [tag for tag in (t_insta, t_fb, t_yt) if tag]
                t_hashtags = "\n".join(tags_list) if tags_list else "#nature #birds"
                
            except:
                print("Metadata WingWonder folder or files not found, proceeding with default text.")
                t_title = "Beautiful Bird!"
                t_hashtags = "#nature #birds"

            # Check text cooling time
            if not is_cooled_down(t_title, 'titles', track_data, TEXT_COOLDOWN_DAYS):
                print(f"Title in cooling period. Skipping folder {folder['name']}.")
                continue
            if not is_cooled_down(t_hashtags, 'hashtags', track_data, TEXT_COOLDOWN_DAYS):
                print(f"Hashtags in cooling period. Skipping folder {folder['name']}.")
                continue

            # Fetch Links and Pick Random VALID Link
            try:
                folder_contents = get_github_contents(folder_path)
                link_file = next((item for item in folder_contents if item['name'] == 'link.txt'), None)
                if not link_file:
                    continue
                
                links_text = fetch_raw_text(link_file['download_url'])
                links = [l.strip() for l in links_text.split('\n') if l.strip()]
                random.shuffle(links)
                
                for link in links:
                    if is_cooled_down(link, 'images', track_data, IMAGE_COOLDOWN_DAYS):
                        selected_image_link = link
                        selected_folder = folder
                        final_title = t_title
                        final_hashtags = t_hashtags
                        break
                
                if selected_image_link:
                    break
                else:
                    print(f"All images in {folder['name']} are in cooldown (18 months).")

            except Exception as e:
                print(f"Error reading links in {folder_path}: {e}")

        if not selected_image_link:
            raise Exception("No valid image/folder found! All images in all folders are in cooldown.")

        print(f"Selected Image Link: {selected_image_link}")

        # Download & Upload Image
        img_response = requests.get(selected_image_link, headers=get_headers())
        img_response.raise_for_status()
        with open(temp_image_path, 'wb') as f:
            f.write(img_response.content)

        hosted_image_url = upload_image_fallback(temp_image_path)
        print(f"Image uploaded successfully: {hosted_image_url}")

        # Post to Webhook with ALL selected Random Data
        webhook_payload = {
            "content": f"**{final_title}**\n\n{final_hashtags}",
            "embeds": [{"image": {"url": hosted_image_url}}]
        }
        webhook_res = requests.post(WEBHOOK_URL, json=webhook_payload)
        webhook_res.raise_for_status()

        # Update JSON State
        now_str = datetime.now().isoformat()
        track_data['last_folder_index'] = current_index
        track_data['images'][selected_image_link] = now_str
        track_data['titles'][final_title] = now_str
        track_data['hashtags'][final_hashtags] = now_str
        save_track_data(track_data, track_sha)
        print("track.json updated successfully.")

        # Success Notification
        success_msg = (
            f"✅ <b>{AUTOMATION_NAME} - Success</b>\n"
            f"<b>Page:</b> {SOCIAL_PAGE_NAME}\n"
            f"<b>Folder:</b> {selected_folder['name']}\n"
            f"<b>Host Used:</b> <a href='{hosted_image_url}'>Link</a>"
        )
        send_telegram(TELEGRAM_SUCCESS_TOKEN, success_msg)

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Automation Failed: {e}")
        fail_msg = (
            f"❌ <b>{AUTOMATION_NAME} - Failed</b>\n"
            f"<b>Page:</b> {SOCIAL_PAGE_NAME}\n"
            f"<b>Error:</b> {str(e)}\n\n"
            f"<code>{error_trace[-800:]}</code>"
        )
        send_telegram(TELEGRAM_FAIL_TOKEN, fail_msg)
        
    finally:
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)

if __name__ == "__main__":
    main()
