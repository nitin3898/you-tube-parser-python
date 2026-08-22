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
<html>
<head>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>YouTube Playlist Exporter</title>
    <style>
        body { font-family: sans-serif; background: #f4f6f9; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); width: 100%; max-width: 400px; text-align: center; }
        input { width: 100%; padding: 12px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; margin-bottom: 15px; }
        button { background: #0066cc; color: white; border: none; padding: 12px; width: 100%; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class='card'>
        <h2>YouTube Playlist Exporter</h2>
        <p>Paste Playlist ID to download Excel table:</p>
        <form action='/generate' method='POST'>
            <input type='text' name='playlist_id' placeholder='Enter Playlist ID' required autocomplete='off'>
            <button type='submit'>Generate & Download</button>
        </form>
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
