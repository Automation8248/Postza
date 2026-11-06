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
COOLDOWN_DAYS = 60 # 60 days ke baad item dubara use ho sakta hai
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
    """Telegram par error message send karne ka function."""
    token = os.getenv("TELEGRAM_FAILD_TOKEN")
    chat_id = os.getenv("FAILED_CHAT_ID")
    repo_name = os.getenv("GITHUB_REPOSITORY", "Unknown_Repo") # GitHub Actions ke liye
    
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
        "message_thread_id": 8,
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
        # Agar item ka last_used time + cooldown time se abhi ka time bada hai, toh item valid hai
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
    """FFmpeg ka use karke Image aur Audio ko merge karke 10 sec ka video banana."""
    output_video = f"final_output_{int(time.time())}.mp4"
    
    # FFmpeg command:
    # -loop 1: image ko loop karta hai
    # -t 10: 10 seconds tak video banayega (agar audio jyada hai toh yahi trim ho jayega)
    # -vf "scale=...": H.264 format mein width/height even (2 se divisible) honi chahiye
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

def post_to_webhook(video_path, title, description):
    """Webhook par Video, Title aur Description post karna."""
    webhook_url = os.getenv("KAVLIO_WEBHOOK")
    if not webhook_url:
        raise ValueError("KAVLIO_WEBHOOK environment variable set nahi hai.")

    with open(video_path, 'rb') as video_file:
        files = {
            'file': (os.path.basename(video_path), video_file, 'video/mp4')
        }
        data = {
            'title': title,
            'description': description
        }
        
        response = requests.post(webhook_url, files=files, data=data)
        
        if response.status_code not in (200, 201, 204):
            raise Exception(f"Webhook post failed! Status: {response.status_code}, Response: {response.text}")

def main():
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

        # 4. Post to Webhook
        print("Posting to Webhook...")
        post_to_webhook(video_path, title, description)

        # 5. Update State & Save (Cooldown Start)
        current_time = time.time()
        state["img"][img_url] = current_time
        state["audio"][audio_url] = current_time
        state["title"][title] = current_time
        state["description"][description] = current_time
        
        save_state(state)
        print("Post successful. State saved & Cooldown updated!")

        # 6. Cleanup temporary files
        os.remove(img_path)
        os.remove(audio_path)
        os.remove(video_path)

    except Exception as e:
        error_details = traceback.format_exc()
        print("Error occurred!")
        print(error_details)
        send_telegram_error(error_details)

if __name__ == "__main__":
    main()
