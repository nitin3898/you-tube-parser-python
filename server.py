import os
import requests
from flask import Flask, render_template_string, request, make_response
import io
import csv
import re

app = Flask(__name__)

API_KEY = os.environ.get("YOUTUBE_API_KEY", "YOUR_API_KEY")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Playlist Exporter</title>
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

        .main-container {
            width: 100%;
            max-width: 460px;
        }

        .card {
            background: #fffdf9;
            padding: 40px 35px;
            border-radius: 24px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
            text-align: center;
            border: 2px solid #e6b800;
            position: relative;
        }

        .sacred-emblem {
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, #ff8c00, #ffcc00);
            border-radius: 50%;
            margin: 0 auto 20px auto;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 30px;
            box-shadow: 0 6px 15px rgba(230, 140, 0, 0.4);
            border: 2px solid #fff;
        }

        h2 {
            color: #3b1402;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-bottom: 15px;
        }

        .divider-line {
            width: 80px;
            height: 3px;
            background: linear-gradient(90deg, transparent, #ff8c00, transparent);
            margin: 0 auto 20px auto;
        }

        p {
            color: #555555;
            margin-bottom: 25px;
            font-size: 15px;
            line-height: 1.6;
        }

        input[type="text"] {
            width: 100%;
            padding: 15px 18px;
            margin-bottom: 20px;
            border: 2px solid #e2d6c8;
            background: #ffffff;
            border-radius: 10px;
            font-size: 15px;
            color: #333;
            transition: all 0.3s ease;
            text-align: center;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: #ff8c00;
            box-shadow: 0 0 10px rgba(255, 140, 0, 0.25);
            background: #fff;
        }

        button {
            background: linear-gradient(135deg, #ff8c00 0%, #cc3300 100%);
            color: white;
            border: none;
            padding: 15px 20px;
            width: 100%;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            letter-spacing: 0.5px;
            box-shadow: 0 6px 20px rgba(204, 51, 0, 0.35);
            transition: transform 0.1s ease, box-shadow 0.2s ease;
        }

        button:hover {
            box-shadow: 0 8px 25px rgba(204, 51, 0, 0.5);
        }

        button:active {
            transform: scale(0.98);
        }

        .footer-credit {
            margin-top: 25px;
            font-size: 13px;
            color: #886040;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
    </style>
</head>
<body>

    <div class="main-container">
        <div class="card">
            <div class="sacred-emblem">🪷</div>
            
            <h2>YouTube Playlist Exporter</h2>
            <div class="divider-line"></div>
            
            <p>Paste your YouTube Playlist ID below to cleanly download your lecture schedule as an Excel spreadsheet.</p>
            
            <form action="/generate" method="POST">
                <input type="text" name="playlist_id" placeholder="Paste Playlist ID here..." required autocomplete="off">
                <button type="submit">Download Spreadsheet</button>
            </form>

            <div class="footer-credit">
                Hare Krishna | Serving the Community
            </div>
        </div>
    </div>

</body>
</html>
"""
@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/generate", methods=["POST"])
def generate():
    playlist_id = request.form.get("playlist_id", "").strip()
    if not playlist_id:
        return "Playlist ID is required", 400

    # Fetch playlist title safely and encode to ASCII to avoid header crashes
    playlist_title = fetch_playlist_title(playlist_id)
    
    # Clean up special characters and convert to safe ASCII bytes for the header
    safe_filename = "".join(c for c in playlist_title if c.isalnum() or c in (' ', '_', '-')).strip()
    if not safe_filename:
        safe_filename = f"YouTube_Playlist_{playlist_id}"
    safe_filename = safe_filename.replace(' ', '_')
    
    # Encode strictly to ASCII, replacing any rogue unicode characters
    safe_filename = safe_filename.encode('ascii', 'ignore').decode('ascii')
    if not safe_filename:
        safe_filename = f"Playlist_{playlist_id}"
    
    filename = f"{safe_filename}.csv"

    csv_data = fetch_playlist_as_csv_data(playlist_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Serial No", "Lecture Title", "Duration"])
    for row in csv_data:
        writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    response.headers["Content-Type"] = "text/csv"
    return response

def fetch_playlist_title(playlist_id):
    url = f"https://www.googleapis.com/youtube/v3/playlists?part=snippet&id={playlist_id}&key={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        items = response.json().get("items", [])
        if items:
            return items[0].get("snippet", {}).get("title", f"Playlist_{playlist_id}")
    return f"Playlist_{playlist_id}"

def fetch_playlist_as_csv_data(playlist_id):
    next_page_token = ""
    serial_no = 1
    all_items = []
    session = requests.Session()

    while True:
        url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet,contentDetails&maxResults=50&playlistId={playlist_id}&key={API_KEY}"
        if next_page_token:
            url += f"&pageToken={next_page_token}"

        response = session.get(url)
        if response.status_code != 200:
            break

        data = response.json()
        items = data.get("items", [])
        
        video_ids = []
        video_titles = []

        for item in items:
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            resource_id = snippet.get("resourceId", {})
            vid_id = resource_id.get("videoId")

            if title and title not in ["Private video", "Deleted video"] and vid_id:
                video_ids.append(vid_id)
                video_titles.append(title)

        durations = fetch_video_durations(session, video_ids)

        for i in range(len(video_ids)):
            dur = durations[i] if i < len(durations) else "0:00"
            all_items.append([serial_no, video_titles[i], dur])
            serial_no += 1

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return all_items

def fetch_video_durations(session, video_ids):
    if not video_ids:
        return []
    
    url = f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id={','.join(video_ids)}&key={API_KEY}"
    response = session.get(url)
    duration_map = {}

    if response.status_code == 200:
        for item in response.json().get("items", []):
            vid = item.get("id")
            iso = item.get("contentDetails", {}).get("duration", "")
            duration_map[vid] = convert_iso_to_readable(iso)

    return [duration_map.get(vid, "0:00") for vid in video_ids]

def convert_iso_to_readable(iso):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso)
    if not match:
        return "0:00"
    h, m, s = match.groups()
    hours = int(h) if h else 0
    minutes = int(m) if m else 0
    seconds = int(s) if s else 0

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
