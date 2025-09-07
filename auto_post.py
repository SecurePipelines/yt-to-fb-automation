# auto_post.py
import os, sys, random, json, subprocess, time
from urllib.parse import urlencode
import requests

# Config via env
YT_API_KEY = os.environ.get("YT_API_KEY")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
KEYWORDS = os.environ.get("KEYWORDS", "nature,drone,timelapse,B-roll,stock footage").split(",")
MIN_CLIP_SEC = int(os.environ.get("MIN_CLIP_SEC", "30"))
MAX_CLIP_SEC = int(os.environ.get("MAX_CLIP_SEC", "40"))
WORKDIR = "work"
POSTED_FILE = "posted.json"

os.makedirs(WORKDIR, exist_ok=True)

def google_youtube_search(q, max_results=50):
    qs = {
        "part": "snippet",
        "type": "video",
        "videoLicense": "creativeCommon",
        "maxResults": str(max_results),
        "q": q,
        "key": YT_API_KEY
    }
    url = "https://www.googleapis.com/youtube/v3/search?" + urlencode(qs)
    r = requests.get(url)
    r.raise_for_status()
    return r.json().get("items", [])

def get_video_details(video_id):
    qs = {
        "part": "contentDetails,snippet,status",
        "id": video_id,
        "key": YT_API_KEY
    }
    url = "https://www.googleapis.com/youtube/v3/videos?" + urlencode(qs)
    r = requests.get(url); r.raise_for_status()
    items = r.json().get("items", [])
    return items[0] if items else None

def iso8601_to_seconds(iso):
    # quick simple parser for PT#H#M#S
    import re
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso)
    if not m: return 0
    h = int(m.group(1) or 0); m_ = int(m.group(2) or 0); s = int(m.group(3) or 0)
    return h*3600 + m_*60 + s

def download_video(video_url, out_dir):
    # requires yt-dlp installed
    out_template = os.path.join(out_dir, "%(id)s.%(ext)s")
    cmd = ["yt-dlp", "-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4",
           "--no-playlist", "-o", out_template, video_url]
    subprocess.check_call(cmd)
    # find resulting file (by id)
    return None  # we'll find file by glob

def find_downloaded_file(out_dir, vid_id):
    import glob
    for p in glob.glob(os.path.join(out_dir, f"{vid_id}.*")):
        if not p.endswith(".part"):
            return p
    return None

def trim_clip(infile, outfile, start_sec, duration_sec):
    # re-encode to H.264/AAC mp4 for FB compatibility
    cmd = [
      "ffmpeg", "-y", "-ss", str(start_sec), "-i", infile,
      "-t", str(duration_sec),
      "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
      "-c:a", "aac", "-b:a", "128k",
      outfile
    ]
    subprocess.check_call(cmd)

def upload_to_facebook(page_id, page_token, video_path, title, description):
    url = f"https://graph.facebook.com/v17.0/{page_id}/videos"
    with open(video_path, "rb") as f:
        files = {'source': f}
        data = {'access_token': page_token, 'title': title, 'description': description}
        r = requests.post(url, data=data, files=files)
    r.raise_for_status(); return r.json()

def load_posted():
    try:
        with open(POSTED_FILE,"r") as f: return set(json.load(f))
    except Exception:
        return set()

def save_posted(s):
    with open(POSTED_FILE,"w") as f: json.dump(list(s), f)

def main():
    if not (YT_API_KEY and FB_PAGE_ID and FB_PAGE_TOKEN):
        print("Missing env vars YT_API_KEY / FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN"); sys.exit(2)

    posted = load_posted()
    candidates = []
    # search a few keywords and build candidate pool
    for kw in KEYWORDS:
        items = google_youtube_search(kw.strip(), max_results=25)
        for it in items:
            vid = it["id"]["videoId"]
            if vid not in posted:
                candidates.append((vid, it["snippet"]["title"], it["snippet"]["channelTitle"], it["snippet"]["thumbnails"].get("high",{}).get("url","")))

    if not candidates:
        print("No new candidates found.")
        return

    # shuffle and try until one works
    random.shuffle(candidates)
    for vid, title, channel, thumb in candidates:
        details = get_video_details(vid)
        if not details: continue
        # verify license if available
        license_type = details.get("status",{}).get("license", "")
        if license_type and license_type != "creativeCommon":
            print(f"Skipping {vid} license={license_type}")
            continue
        duration_iso = details.get("contentDetails",{}).get("duration", "PT0S")
        total_sec = iso8601_to_seconds(duration_iso)
        if total_sec < MIN_CLIP_SEC:
            print(f"Skipping {vid} too short ({total_sec}s)")
            continue

        # download
        video_url = f"https://www.youtube.com/watch?v={vid}"
        print("Downloading", video_url)
        download_video(video_url, WORKDIR)
        infile = find_downloaded_file(WORKDIR, vid)
        if not infile:
            print("Download failed for", vid); continue

        clip_len = random.randint(MIN_CLIP_SEC, MAX_CLIP_SEC)
        max_start = max(0, total_sec - clip_len)
        start = random.randint(0, max_start) if max_start>0 else 0
        outclip = os.path.join(WORKDIR, f"{vid}_clip.mp4")
        print(f"Trimming start={start}s len={clip_len}s -> {outclip}")
        trim_clip(infile, outclip, start, clip_len)

        # build description with attribution (per CC BY)
        desc = f"Clip from \"{title}\" by {channel}\nOriginal: https://www.youtube.com/watch?v={vid}\n\nAuto-posted — source Creative Commons."
        try:
            resp = upload_to_facebook(FB_PAGE_ID, FB_PAGE_TOKEN, outclip, title, desc)
            print("Uploaded:", resp)
            posted.add(vid)
            save_posted(posted)
            return
        except Exception as e:
            print("Upload failed:", e)
            # continue to next candidate

    print("Done. No candidate succeeded.")

if __name__ == "__main__":
    main()
