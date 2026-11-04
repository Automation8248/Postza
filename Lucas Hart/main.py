import os
import requests
import json
import random
import traceback
import re
from datetime import datetime
from github import Github
from moviepy.editor import ImageClip, TextClip, AudioFileClip, CompositeVideoClip

# ================= Configuration =================
DURATION = 10
FIXED_AUTHOR = "Lucas Hart"
REPO_NAME = "Automation8248/Codvix"  # Repository name updated based on your link

# Environment Variables
GH_TOKEN = os.environ.get("GH_TOKEN")
TELEGRAM_FAILD_TOKEN = os.environ.get("TELEGRAM_FAILD_TOKEN")
TELEGRAM_FAILD_ID = os.environ.get("TELEGRAM_FAILD_ID")
THREAD_ID = 8  # Fixed Thread ID for Telegram Alerts

# GitHub Paths
TRACK_FILE_PATH = "Video Generator/Lucas Hart/track.json"  # Updated Path
CAPTION_FILE_PATH = "Lucas Hart/caption.txt"              # caption.txt file path
VIDEO_FOLDER_PATH = "Lucas Hart/video"                    # video folder path
# =================================================

def send_telegram_error(error_msg):
    """Sends an error alert to the specific Telegram Thread."""
    if not TELEGRAM_FAILD_TOKEN or not TELEGRAM_FAILD_ID:
        print("Telegram tokens are missing. Cannot send alert.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_FAILD_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_FAILD_ID,
        "message_thread_id": THREAD_ID,
        "text": f"🚨 *Lucas Hart Video Automation Failed!*\n\n`{error_msg}`",
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram alert failed: {e}")

def get_headers():
    """Returns standard browser headers for requests to avoid blocking."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

def get_free_quote_only():
    try:
        res = requests.get("https://zenquotes.io/api/random", headers=get_headers(), timeout=10)
        return res.json()[0]['q']
    except: 
        return "Your only limit is your mind."

def download_image_file(link, output_path):
    """Downloads an image from a Google Drive link or any direct URL."""
    file_id_match = re.search(r'id=([a-zA-Z0-9_-]+)', link) or re.search(r'/d/([a-zA-Z0-9_-]+)', link)
    
    if file_id_match:
        file_id = file_id_match.group(1)
        url = f"https://drive.google.com/uc?id={file_id}"
    else:
        url = link

    res = requests.get(url, headers=get_headers(), allow_redirects=True)
    if res.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(res.content)
        return output_path
    raise Exception(f"Failed to download image. Status code: {res.status_code}")

def download_audio_file(link, output_path):
    """Downloads audio from a direct link."""
    res = requests.get(link, headers=get_headers(), allow_redirects=True)
    if res.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(res.content)
        return output_path
    raise Exception("Failed to download direct audio file.")

def get_file_with_cooling(file_type, links_list, track_data):
    """Returns a link that is not in the 60-day cooling period and updates track_data."""
    today = datetime.now().date()
    cooling_dict = track_data.setdefault(f"cooling_{file_type}", {})
    
    available_links = []
    for link in links_list:
        link = link.strip()
        if not link: continue
        
        last_used_str = cooling_dict.get(link)
        if last_used_str:
            last_used_date = datetime.strptime(last_used_str, "%Y-%m-%d").date()
            # 60 DAYS COOLING LOGIC
            if (today - last_used_date).days < 60:
                continue
        available_links.append(link)
        
    print(f"[DEBUG] {file_type.capitalize()} available after 60-day cooling filter: {len(available_links)}")
    
    if not available_links:
        return None, track_data
        
    selected_link = random.choice(available_links)
    # Apply NEW 60-day cooling timestamp (Updates automatically if reused after 60 days)
    track_data[f"cooling_{file_type}"][selected_link] = today.strftime("%Y-%m-%d")
    return selected_link, track_data

def update_github_file(repo, path, content, message):
    """Creates or updates a file directly in the GitHub repository."""
    try:
        file = repo.get_contents(path)
        repo.update_file(path, message, content, file.sha)
    except:
        repo.create_file(path, message, content)

def main():
    try:
        # 1. Initialize GitHub
        if not GH_TOKEN:
            raise Exception("GH_TOKEN is not set.")
        g = Github(GH_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # 2. Load tracking state
        try:
            track_file = repo.get_contents(TRACK_FILE_PATH)
            track_data = json.loads(track_file.decoded_content.decode('utf-8'))
        except:
            track_data = {"current_video": 1, "cooling_images": {}, "cooling_audios": {}}

        # 3. Determine Video Name (1 to 90 Loop)
        current_video_num = track_data.get("current_video", 1)
        if current_video_num > 90:
            current_video_num = 1
        video_filename = f"shorts.{current_video_num}.mp4"
        
        # 4. Fetch Links
        with open("images.txt", "r") as f:
            image_links = f.readlines()

        with open("bg_link.txt", "r") as f:
            audio_links = f.readlines()

        # 5. Get Cooled Assets & Download
        bg_link, track_data = get_file_with_cooling("images", image_links, track_data)
        if not bg_link:
            raise Exception("Images list khali hai ya sabhi images abhi 60 din ke cooling me hain!")
        bg_path = download_image_file(bg_link, "temp_bg.jpg")

        audio_link, track_data = get_file_with_cooling("audios", audio_links, track_data)
        audio_path = download_audio_file(audio_link, "temp_audio.mp3") if audio_link else None

        # 6. Fetch Quote
        quote_text = get_free_quote_only()

        # 7. Create Video (User's Exact Logic Added Here)
        print(f"[DEBUG] Compiling Video {video_filename} with MoviePy...")
        
        bg = ImageClip(bg_path).set_duration(DURATION).resize(height=1920).fl_image(lambda image: (image * 0.6).astype('uint8'))
        
        full_display_text = f"\"{quote_text}\"\n\n{FIXED_AUTHOR}"
        txt = TextClip(full_display_text, fontsize=80, color='white', font='Arial-Bold', 
                       method='caption', size=(850, None)).set_duration(DURATION).set_position('center')
        
        final = CompositeVideoClip([bg, txt])
        
        if audio_path:
            try:
                audio = AudioFileClip(audio_path).subclip(0, min(DURATION, AudioFileClip(audio_path).duration))
                final = final.set_audio(audio)
            except Exception as e:
                print(f"Audio Edit Error: {e}")
        
        final.write_videofile(video_filename, fps=24, codec="libx264", audio_codec="aac")

        # 8. Upload Video to GitHub Repo
        print(f"[DEBUG] Uploading {video_filename} to GitHub...")
        with open(video_filename, "rb") as f:
            update_github_file(repo, f"{VIDEO_FOLDER_PATH}/{video_filename}", f.read(), f"Upload {video_filename}")
        
        # 9. Update caption.txt
        try:
            q_file = repo.get_contents(CAPTION_FILE_PATH)
            old_quotes = q_file.decoded_content.decode('utf-8')
            new_quotes = old_quotes + f"\n{quote_text}"
            repo.update_file(CAPTION_FILE_PATH, f"Added caption for {video_filename}", new_quotes, q_file.sha)
        except:
            repo.create_file(CAPTION_FILE_PATH, "Created caption.txt", quote_text)
            
        # 10. Update & Save track.json (Explicit Tracking Added)
        track_data["current_video"] = current_video_num + 1
        track_data["last_generated_video"] = video_filename
        track_data["last_used_image"] = bg_link
        if audio_link:
            track_data["last_used_audio"] = audio_link
            
        updated_track_json = json.dumps(track_data, indent=4)
        update_github_file(repo, TRACK_FILE_PATH, updated_track_json, f"Update track.json post {video_filename}")

        print(f"Success: {video_filename} generated and uploaded.")

        # Cleanup
        os.remove(bg_path)
        if audio_path: os.remove(audio_path)
        os.remove(video_filename)

    except Exception as e:
        error_trace = traceback.format_exc()
        print(error_trace)
        send_telegram_error(str(e))

if __name__ == "__main__":
    main()
