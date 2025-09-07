import os
import random
import subprocess
import requests
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "funny+clips")

# Create a folder for downloads
os.makedirs("downloads", exist_ok=True)

def get_random_youtube_video():
    """Fetch random copyright-free videos from YouTube."""
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(
        q=SEARCH_QUERY,
        part="snippet",
        maxResults=10,
        videoLicense="creativeCommon",
        type="video",
        videoDuration="medium",  # Only videos > 4 mins
        order="relevance"
    )
    response = request.execute()
    videos = response.get("items", [])
    if not videos:
        print("No videos found!")
        return None
    return random.choice(videos)

def download_video(video_id):
    """Download video using yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = os.path.join("downloads", "video.mp4")
    cmd = ["yt-dlp", "-f", "best", "-o", output_path, url]
    subprocess.run(cmd, check=True)
    return output_path

def trim_video(input_path):
    """Trim random 30–40 sec clip."""
    output_path = os.path.join("downloads", "clip.mp4")
    start_time = random.randint(30, 120)  # Start between 30s and 2min
    clip_length = random.randint(30, 40)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-t", str(clip_length),
        "-i", input_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-strict", "experimental",
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path

def post_to_facebook(video_path, description="Enjoy this clip!"):
    """Upload video to Facebook Page."""
    url = f"https://graph-video.facebook.com/v17.0/{FACEBOOK_PAGE_ID}/videos"
    with open(video_path, "rb") as video_file:
        response = requests.post(
            url,
            files={"file": video_file},
            data={
                "access_token": FACEBOOK_ACCESS_TOKEN,
                "description": description
            }
        )
    if response.status_code == 200:
        print("✅ Video posted successfully!")
    else:
        print("❌ Failed to post video:", response.json())

def main():
    print("🔍 Fetching a random Creative Commons video...")
    video = get_random_youtube_video()
    if not video:
        return
    video_id = video["id"]["videoId"]
    title = video["snippet"]["title"]
    print(f"🎥 Selected Video: {title}")

    print("⬇️ Downloading video...")
    downloaded = download_video(video_id)

    print("✂️ Trimming 30-40 sec clip...")
    clip = trim_video(downloaded)

    print("🚀 Uploading clip to Facebook...")
    post_to_facebook(clip, description=title + " | #Shorts #Reels")

    print("✅ Process completed successfully!")

if __name__ == "__main__":
    main()
