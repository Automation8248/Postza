import os
import json
import time
import random
import requests
import subprocess
import traceback

# Configuration
FOLDER_NAME = "Kavlio"
STATE_FILE = os.path.join(FOLDER_NAME, "facbook.json")
COOLDOWN_DAYS = 60 # 60 days cooling period
VIDEO_DURATION = 10 # Video duration in seconds

def load_state():
    """Load JSON state file to track cooldowns."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"audio": {}, "img": {}, "title": {}, "description": {}}

def save_state(state):
    """Save the updated state back to JSON."""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4)

def send_telegram_error(error_message):
    """Telegram par error message send karne ka function (Thread ID: 8)."""
    token = os.getenv("TELEGRAM_FAILD_TOKEN")
    chat_id = os.getenv("FAILED_CHAT_ID")
    repo_name = os.getenv("GITHUB_REPOSITORY", "Unknown_Repo")
    
    if not token or not chat_id:
        print("Telegram tokens missing, cannot send error log.")
        return

    text = (
        f"🚨 **Automation Failed!**\n"
        f"**Repo Name**: {repo_name}\n"
        f"**Folder Name**: {FOLDER_NAME}\n\n"
        f"**Error Details**:\n`{error_message}`"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "message_thread_id": 8,  # Thread ID 8 ka use
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram error: {e}")

def get_random_item(filename, category, state):
    """Cooling time check karke random file ya text link nikalna."""
    filepath = os.path.join(FOLDER_NAME, filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"{filepath} file not found!")

    with open(filepath, 'r', encoding='utf-8') as f:
        items = [line.strip() for line in f if line.strip()]

    valid_items = []
    current_time = time.time()
    cooldown_seconds = COOLDOWN_DAYS * 24 * 60 * 60

    for item in items:
        last_used = state[category].get(item, 0)
        if (current_time - last_used) >= cooldown_seconds:
            valid_items.append(item)

    if not valid_items:
        raise Exception(f"Sabhi items {filename} mein cooling period mein hain. Koi naya data available nahi hai.")

    return random.choice(valid_items)

def download_file(url, extension):
    """URL se file download karna (Image/Audio)."""
    temp_filename = f"temp_{int(time.time())}{extension}"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(temp_filename, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return temp_filename
    else:
        raise Exception(f"Failed to download from {url} (Status: {response.status_code})")

def create_video(img_path, audio_path):
    """FFmpeg ka use karke Image aur Audio ko merge karke video banana."""
    output_video = f"final_output_{int(time.time())}.mp4"
    
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path, "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", 
        "-t", str(VIDEO_DURATION), "-pix_fmt", "yuv420p", "-shortest", output_video
    ]
    
    process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise Exception(f"FFmpeg failed:\n{process.stderr.decode('utf-8')}")
        
    return output_video

def upload_video_with_fallback(video_path):
    """10 servers ka loop jo ek fail hone par next try karega."""
    filename = os.path.basename(video_path)
    timeout_sec = 60

    # 10 File Hosting Servers ki strategies
    def upload_catbox():
        with open(video_path, 'rb') as f:
            r = requests.post('https://catbox.moe/user/api.php', data={'reqtype': 'fileupload'}, files={'fileToUpload': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.text.strip()

    def upload_envs():
        with open(video_path, 'rb') as f:
            r = requests.post('https://envs.sh', files={'file': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.text.strip()

    def upload_0x0():
        with open(video_path, 'rb') as f:
            r = requests.post('https://0x0.st', files={'file': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.text.strip()

    def upload_ttm():
        with open(video_path, 'rb') as f:
            r = requests.post('https://ttm.sh', files={'file': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.text.strip()

    def upload_transfer_sh():
        with open(video_path, 'rb') as f:
            r = requests.put(f'https://transfer.sh/{filename}', data=f, timeout=timeout_sec)
        r.raise_for_status()
        return r.text.strip()

    def upload_pomf():
        with open(video_path, 'rb') as f:
            r = requests.post('https://pomf.lain.la/upload.php', files={'files[]': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.json()['files'][0]['url']

    def upload_tmpfiles():
        with open(video_path, 'rb') as f:
            r = requests.post('https://tmpfiles.org/api/v1/upload', files={'file': f}, timeout=timeout_sec)
        r.raise_for_status()
        url = r.json()['data']['url']
        return url.replace('tmpfiles.org/', 'tmpfiles.org/dl/') # Convert to direct download link

    def upload_litterbox():
        with open(video_path, 'rb') as f:
            r = requests.post('https://litterbox.catbox.moe/resources/internals/api.php', data={'reqtype': 'fileupload', 'time': '72h'}, files={'fileToUpload': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.text.strip()

    def upload_uguu():
        with open(video_path, 'rb') as f:
            r = requests.post('https://uguu.se/upload.php', files={'files[]': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.json()['files'][0]['url']

    def upload_fileio():
        with open(video_path, 'rb') as f:
            r = requests.post('https://file.io', files={'file': f}, timeout=timeout_sec)
        r.raise_for_status()
        return r.json()['link']

    servers = [
        ("catbox.moe", upload_catbox),
        ("envs.sh", upload_envs),
        ("0x0.st", upload_0x0),
        ("pomf.lain.la", upload_pomf),
        ("ttm.sh", upload_ttm),
        ("transfer.sh", upload_transfer_sh),
        ("tmpfiles.org", upload_tmpfiles),
        ("litterbox.catbox.moe", upload_litterbox),
        ("uguu.se", upload_uguu),
        ("file.io", upload_fileio)
    ]

    for server_name, upload_func in servers:
        try:
            print(f"Uploading to {server_name}...")
            video_url = upload_func()
            if video_url and video_url.startswith("http"):
                print(f"✅ Upload successful on {server_name}: {video_url}")
                return video_url
        except Exception as e:
            print(f"❌ Failed on {server_name}: {e}")
            continue

    raise Exception("Sabhi 10 video upload servers fail ho gaye!")

def post_to_webhook(video_url, title, description):
    """Webhook par Video URL, Title aur Description post karna."""
    webhook_url = os.getenv("KAVLIO_FACBOOK_WEBHOOK")
    if not webhook_url:
        raise ValueError("KAVLIO_FACBOOK_WEBHOOK environment variable set nahi hai.")

    # Ab hum file ki jagah direct URL bhej rahe hain
    data = {
        'title': title,
        'description': description,
        'video_url': video_url
    }
    
    response = requests.post(webhook_url, data=data)
    
    if response.status_code not in (200, 201, 204):
        raise Exception(f"Webhook post failed! Status: {response.status_code}, Response: {response.text}")

def main():
    img_path = audio_path = video_path = None
    try:
        print("Starting Automation...")
        state = load_state()

        # 1. Get Random Valid Items
        img_url = get_random_item("post.txt", "img", state)
        audio_url = get_random_item("audio.txt", "audio", state)
        title = get_random_item("title.txt", "title", state)
        description = get_random_item("discription.txt", "description", state)
        
        print("Selected items for processing.")
        print(f"Title: {title}")

        # 2. Download Image and Audio
        img_path = download_file(img_url, ".jpg")
        audio_path = download_file(audio_url, ".mp3")

        # 3. Create Video (Merge & Trim)
        print("Creating Video...")
        video_path = create_video(img_path, audio_path)

        # 4. Upload Video to Server with Fallback (10 Servers loop)
        print("Uploading Video to Servers...")
        video_url = upload_video_with_fallback(video_path)

        # 5. Post to Webhook (URL version)
        print("Posting Video URL to Webhook...")
        post_to_webhook(video_url, title, description)

        # 6. Update State & Save (Cooldown Start)
        current_time = time.time()
        state["img"][img_url] = current_time
        state["audio"][audio_url] = current_time
        state["title"][title] = current_time
        state["description"][description] = current_time
        
        save_state(state)
        print("✅ Post successful. State saved & Cooldown updated!")

    except Exception as e:
        error_details = traceback.format_exc()
        print("Error occurred!")
        print(error_details)
        send_telegram_error(error_details)
    finally:
        # 7. Cleanup temporary files chahe error aaye ya na aaye
        for path in [img_path, audio_path, video_path]:
            if path and os.path.exists(path):
                os.remove(path)

if __name__ == "__main__":
    main()
