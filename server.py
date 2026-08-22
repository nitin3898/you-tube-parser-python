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
            /* Rich warm devotional gradient background: Deep Maroon to Saffron */
            background: linear-gradient(135deg, #4a0e0e 0%, #b33900 50%, #ff8c00 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .main-container {
            width: 100%;
            max-width: 440px;
            padding: 20px;
        }

        .card {
            background: rgba(255, 255, 255, 0.98);
            padding: 40px 30px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            text-align: center;
            border-top: 5px solid #ff8c00; /* Saffron top border accent */
        }

        h2 {
            color: #2c1d0c;
            margin-bottom: 8px;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        p {
            color: #555;
            margin-bottom: 25px;
            font-size: 15px;
            line-height: 1.5;
        }

        .divider {
            width: 40px;
            height: 3px;
            background: #ff8c00;
            margin: 0 auto 20px auto;
            border-radius: 2px;
        }

        input[type="text"] {
            width: 100%;
            padding: 14px;
            margin-bottom: 20px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 15px;
            transition: all 0.3s ease;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: #ff8c00;
            box-shadow: 0 0 8px rgba(255, 140, 0, 0.2);
        }

        button {
            background: linear-gradient(135deg, #ff8c00 0%, #e65100 100%);
            color: white;
            border: none;
            padding: 14px 20px;
            width: 100%;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            letter-spacing: 0.5px;
            transition: transform 0.1s ease, box-shadow 0.2s ease;
            box-shadow: 0 4px 15px rgba(230, 81, 0, 0.4);
        }

        button:hover {
            box-shadow: 0 6px 20px rgba(230, 81, 0, 0.6);
        }

        button:active {
            transform: scale(0.98);
        }

        .footer-credit {
            margin-top: 20px;
            font-size: 13px;
            color: #777;
            letter-spacing: 0.3px;
        }
    </style>
</head>
<body>

    <div class="main-container">
        <div class="card">
            <h2>YouTube Playlist Exporter</h2>
            <div class="divider"></div>
            <p>Paste your YouTube Playlist ID below to download your lecture list as a neat spreadsheet.</p>
            
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

    # Fetch playlist title dynamically for the filename
    playlist_title = fetch_playlist_title(playlist_id)
    safe_filename = "".join(c for c in playlist_title if c.isalnum() or c in (' ', '_', '-')).strip()
    if not safe_filename:
        safe_filename = f"YouTube_Playlist_{playlist_id}"
    safe_filename = safe_filename.replace(' ', '_') + ".csv"

    csv_data = fetch_playlist_as_csv_data(playlist_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Serial No", "Lecture Title", "Duration"])
    for row in csv_data:
        writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=\"{safe_filename}\""
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
