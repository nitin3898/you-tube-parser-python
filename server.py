import os
import io
import csv
import requests
from flask import Flask, request, render_template_string, make_response

app = Flask(__name__)

# Fetch API key from environment variable (secure practice) or fallback string
API_KEY = os.environ.get("YOUTUBE_API_KEY", "YOUR_API_KEY_HERE")

def parse_duration(iso_duration):
    """Converts YouTube ISO 8601 duration (e.g., PT1H2M10S) to HH:MM:SS format."""
    import re
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
    """Safely fetches the playlist title from YouTube API."""
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
    """Fetches all items from a playlist with full pagination support."""
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
                
                # Skip deleted or private placeholders to prevent clutter
                if title in ["[Private video]", "[Deleted video]"]:
                    continue
                    
                resource_id = snippet.get("resourceId", {})
                vid_id = resource_id.get("videoId")
                if vid_id:
                    video_ids.append(vid_id)
                    item_map[vid_id] = title

            if video_ids:
                # Fetch durations in batches of 50
                dur_url = (
                    f"https://www.googleapis.com/youtube/v3/videos"
                    f"?part=contentDetails&id={','.join(video_ids)}&key={API_KEY}"
                )
                dur_response = requests.get(dur_url, timeout=15)
                if dur_response.status_code == 200:
                    for vid_item in dur_response.json().get("items", []):
                        vid_id = vid_item.get("id")
                        iso_dur = vid_item.get("contentDetails", {}).get("duration", "PT0S")
                        formatted_dur = parse_duration(iso_dur)
                        title = item_map.get(vid_id, "Unknown Title")
                        videos.append((title, formatted_dur))

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
        except Exception:
            break

    # Format into rows with serial numbers
    csv_rows = []
    for index, (title, duration) in enumerate(videos, start=1):
        csv_rows.append([index, title, duration])
        
    return csv_rows

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

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/generate", methods=["POST"])
def generate():
    playlist_id = request.form.get("playlist_id", "").strip()
    if not playlist_id:
        return "Playlist ID is required", 400

    # Sanitize dynamic title for safe HTTP headers
    playlist_title = fetch_playlist_title(playlist_id)
    safe_filename = "".join(c for c in playlist_title if c.isalnum() or c in (' ', '_', '-')).strip()
    if not safe_filename:
        safe_filename = f"YouTube_Playlist_{playlist_id}"
    safe_filename = safe_filename.replace(' ', '_')
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

    # Encode with UTF-8 BOM so Excel opens diacritics and symbols cleanly
    csv_bytes = output.getvalue().encode('utf-8-sig')

    response = make_response(csv_bytes)
    response.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
