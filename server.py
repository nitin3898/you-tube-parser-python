import os
import io
import csv
import re
import requests
from flask import Flask, request, render_template_string, make_response
import yt_dlp

app = Flask(__name__)

API_KEY = os.environ.get("YOUTUBE_API_KEY", "YOUR_API_KEY_HERE")

def parse_duration(iso_duration):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return "00:00:00"
    
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def fetch_playlist_title(playlist_id):
    url = f"https://www.googleapis.com/youtube/v3/playlists?part=snippet&id={playlist_id}&key={API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            if items:
                return items[0].get("snippet", {}).get("title", f"Playlist_{playlist_id}")
    except Exception:
        pass
    return f"Playlist_{playlist_id}"

def fetch_playlist_as_csv_data(playlist_id):
    videos = []
    next_page_token = ""
    
    while True:
        url = (
            f"https://www.googleapis.com/youtube/v3/playlistItems"
            f"?part=snippet,contentDetails&maxResults=50&playlistId={playlist_id}&key={API_KEY}"
        )
        if next_page_token:
            url += f"&pageToken={next_page_token}"
            
        try:
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                break
                
            data = response.json()
            items = data.get("items", [])
            if not items:
                break

            video_ids = []
            item_map = {}
            for item in items:
                snippet = item.get("snippet", {})
                title = snippet.get("title", "")
                if title in ["[Private video]", "[Deleted video]"]:
                    continue
                vid_id = snippet.get("resourceId", {}).get("videoId")
                if vid_id:
                    video_ids.append(vid_id)
                    item_map[vid_id] = title

            if video_ids:
                dur_url = f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id={','.join(video_ids)}&key={API_KEY}"
                dur_response = requests.get(dur_url, timeout=15)
                if dur_response.status_code == 200:
                    for vid_item in dur_response.json().get("items", []):
                        vid_id = vid_item.get("id")
                        iso_dur = vid_item.get("contentDetails", {}).get("duration", "PT0S")
                        videos.append((item_map.get(vid_id, "Unknown Title"), parse_duration(iso_dur)))

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
        except Exception:
            break

    return [[i, t, d] for i, (t, d) in enumerate(videos, start=1)]

def extract_video_id(input_str):
    input_str = input_str.strip()
    if len(input_str) == 11 and " " not in input_str:
        return input_str
    
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, input_str)
        if match:
            return match.group(1)
    return input_str

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Lecture Utility Suite</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(145deg, #380404 0%, #8b2500 50%, #d96b00 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .main-container { width: 100%; max-width: 520px; }
        .card {
            background: #fffdf9;
            padding: 35px 30px;
            border-radius: 24px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
            text-align: center;
            border: 2px solid #e6b800;
            margin-bottom: 20px;
        }
        .sacred-emblem {
            width: 56px; height: 56px;
            background: linear-gradient(135deg, #ff8c00, #ffcc00);
            border-radius: 50%;
            margin: 0 auto 15px auto;
            display: flex; justify-content: center; align-items: center;
            font-size: 26px; box-shadow: 0 6px 15px rgba(230, 140, 0, 0.4);
            border: 2px solid #fff;
        }
        h2 { color: #3b1402; font-size: 22px; font-weight: 700; margin-bottom: 10px; }
        .divider-line {
            width: 60px; height: 3px;
            background: linear-gradient(90deg, transparent, #ff8c00, transparent);
            margin: 0 auto 15px auto;
        }
        p { color: #555555; margin-bottom: 20px; font-size: 14px; line-height: 1.5; }
        input[type="text"] {
            width: 100%; padding: 14px 16px; margin-bottom: 15px;
            border: 2px solid #e2d6c8; background: #ffffff;
            border-radius: 10px; font-size: 14px; color: #333;
            text-align: center; transition: all 0.3s ease;
        }
        input[type="text"]:focus {
            outline: none; border-color: #ff8c00;
            box-shadow: 0 0 10px rgba(255, 140, 0, 0.25);
        }
        .btn-group { display: flex; gap: 10px; }
        button {
            background: linear-gradient(135deg, #ff8c00 0%, #cc3300 100%);
            color: white; border: none; padding: 14px 16px; width: 100%;
            border-radius: 10px; font-size: 15px; font-weight: 700; cursor: pointer;
            box-shadow: 0 4px 15px rgba(204, 51, 0, 0.3);
        }
        button.secondary {
            background: linear-gradient(135deg, #0073e6 0%, #00438a 100%);
            box-shadow: 0 4px 15px rgba(0, 115, 230, 0.3);
        }
        button:active { transform: scale(0.98); }
        .footer-credit { font-size: 12px; color: #886040; font-weight: 600; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="card">
            <div class="sacred-emblem">🪷</div>
            <h2>Playlist Schedule Exporter</h2>
            <div class="divider-line"></div>
            <p>Paste a YouTube Playlist ID or URL to download your complete lectures checklist as a clean CSV spreadsheet.</p>
            <form action="/generate-playlist" method="POST">
                <input type="text" name="playlist_id" placeholder="Paste Playlist ID or URL..." required autocomplete="off">
                <button type="submit">Download Playlist CSV</button>
            </form>
        </div>

        <div class="card" style="margin-bottom: 0;">
            <div class="sacred-emblem" style="background: linear-gradient(135deg, #0073e6, #00bfff);">📜</div>
            <h2>Video Transcript Downloader</h2>
            <div class="divider-line" style="background: linear-gradient(90deg, transparent, #0073e6, transparent);"></div>
            <p>Extract formatted timestamps and text for any individual lecture video.</p>
            <form action="/generate-transcript" method="POST">
                <input type="text" name="video_input" placeholder="Paste Video ID or URL..." required autocomplete="off">
                <div class="btn-group">
                    <button type="submit" name="lang" value="hi" class="secondary">Hindi Transcript</button>
                    <button type="submit" name="lang" value="en" class="secondary">English Transcript</button>
                </div>
            </form>
            <div class="footer-credit">Hare Krishna | Serving the Community</div>
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/generate-playlist", methods=["POST"])
def generate_playlist():
    raw_input = request.form.get("playlist_id", "").strip()
    playlist_id = raw_input
    if "list=" in raw_input:
        match = re.search(r'list=([a-zA-Z0-9_-]+)', raw_input)
        if match:
            playlist_id = match.group(1)

    if not playlist_id:
        return "Playlist ID is required", 400

    playlist_title = fetch_playlist_title(playlist_id)
    safe_filename = "".join(c for c in playlist_title if c.isalnum() or c in (' ', '_', '-')).strip()
    if not safe_filename:
        safe_filename = f"Playlist_{playlist_id}"
    safe_filename = safe_filename.replace(' ', '_').encode('ascii', 'ignore').decode('ascii')
    if not safe_filename:
        safe_filename = f"Playlist_{playlist_id}"
    
    filename = f"{safe_filename}.csv"
    csv_data = fetch_playlist_as_csv_data(playlist_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Serial No", "Lecture Title", "Duration"])
    for row in csv_data:
        writer.writerow(row)

    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

@app.route("/generate-transcript", methods=["POST"])
def generate_transcript():
    raw_input = request.form.get("video_input", "").strip()
    lang = request.form.get("lang", "en").strip()
    video_id = extract_video_id(raw_input)

    if not video_id:
        return "Video ID or URL is required", 400

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Configure yt-dlp to extract subtitles metadata without downloading media
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [lang, 'en', 'hi'],
    }

    subtitles_data = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # Check requested language subtitles first, then automatic captions
            subs = info.get('requested_subtitles') or info.get('subtitles') or info.get('automatic_captions')
            
            if subs:
                # Find best matching subtitle JSON format url
                target_sub = None
                if lang in subs:
                    target_sub = subs[lang]
                else:
                    for k in subs:
                        if subs[k]:
                            target_sub = subs[k]
                            break
                
                if target_sub:
                    # yt-dlp provides formats like 'json3' or 'vtt'
                    formats = target_sub if isinstance(target_sub, list) else [target_sub]
                    sub_url = None
                    for fmt in formats:
                        if fmt.get('ext') == 'json3':
                            sub_url = fmt.get('url')
                            break
                    if not sub_url and formats:
                        sub_url = formats[0].get('url')

                    if sub_url:
                        sub_resp = requests.get(sub_url, timeout=15)
                        if sub_resp.status_code == 200:
                            subtitles_data = sub_resp.json()

        if not subtitles_data or 'events' not in subtitles_data:
            raise Exception("No subtitle events found.")

        events = subtitles_data.get('events', [])
        output_lines = [f"--- YOUTUBE VIDEO TRANSCRIPT ({lang.upper()}) ---"]
        
        for event in events:
            if 'segs' in event:
                start_ms = event.get('tStartMs', 0)
                total_seconds = int(start_ms) // 1000
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                timestamp_str = f"[{minutes:02d}:{seconds:02d}]"
                
                text_chunk = "".join([seg.get('utf8', '') for seg in event['segs']]).strip()
                if text_chunk and text_chunk != '\n':
                    output_lines.append(f"{timestamp_str} {text_chunk}")

        if len(output_lines) <= 1:
            raise Exception("Empty transcript parsed.")

        final_text = "\n".join(output_lines)
        response = make_response(final_text)
        response.headers["Content-Disposition"] = f"attachment; filename=\"Transcript_{video_id}_{lang}.txt\""
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        return response

    except Exception:
        return render_template_string("""
            <body style="font-family:sans-serif; text-align:center; padding:50px; background:#fffdf9;">
                <h2 style="color:#b30000;">No captions found for this video.</h2>
                <p style="color:#555;">YouTube closed captions or auto-generated transcripts could not be extracted for this video ID.</p>
                <a href="/" style="display:inline-block; margin-top:20px; padding:10px 20px; background:#ff8c00; color:#fff; text-decoration:none; border-radius:8px;">Back to Home</a>
            </body>
        """), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
