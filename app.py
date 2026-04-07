from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-2024'

API_KEY = os.getenv("API_KEY")

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage 
                 (ip TEXT, date TEXT, count INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

init_db()

def get_usage(ip):
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT SUM(count) FROM usage WHERE ip=? AND date=?", (ip, today))
    usage = c.fetchone()[0] or 0
    conn.close()
    return int(usage)

def record_usage(ip):
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("INSERT INTO usage (ip, date) VALUES (?, ?)", (ip, today))
    conn.commit()
    conn.close()

# ---------------- YOUTUBE TOOL ----------------
class YouTubeTool:
    def __init__(self, api_key):
        self.youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=api_key
        )

    def extract_video_id(self, url):
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
        return match.group(1) if match else None

    def get_channel_from_video(self, video_id):
        res = self.youtube.videos().list(
            part="snippet", id=video_id
        ).execute()
        return res['items'][0]['snippet']['channelId']

    def resolve_channel(self, input_text):
        input_text = input_text.strip()

        if input_text.startswith("UC"):
            return input_text

        if "@" in input_text:
            handle = input_text.split("@")[-1].split("?")[0]
            res = self.youtube.search().list(
                part="snippet",
                q=handle,
                type="channel",
                maxResults=1
            ).execute()
            return res['items'][0]['snippet']['channelId']

        if "youtube.com/channel/" in input_text:
            return input_text.split("channel/")[1].split("/")[0]

        video_id = self.extract_video_id(input_text)
        if video_id:
            return self.get_channel_from_video(video_id)

        res = self.youtube.search().list(
            part="snippet",
            q=input_text,
            type="channel",
            maxResults=1
        ).execute()

        return res['items'][0]['snippet']['channelId']

    # ✅ GLOBAL SEARCH (UNCHANGED)
    def search_global_videos(self, keyword):
        videos = []
        next_page_token = None

        while len(videos) < 50:
            res = self.youtube.search().list(
                part="snippet,id",
                q=keyword,
                type="video",
                maxResults=25,
                pageToken=next_page_token
            ).execute()

            videos.extend(res.get('items', []))
            next_page_token = res.get("nextPageToken")

            if not next_page_token:
                break

        return videos

    def search_channels(self, keyword):
        res = self.youtube.search().list(
            part="snippet",
            q=keyword,
            type="channel",
            maxResults=10
        ).execute()

        channels = []
        for item in res.get("items", []):
            channels.append({
                "channelId": item["snippet"]["channelId"],
                "title": item["snippet"]["title"]
            })

        return channels

    # 🔥 ONLY FIX APPLIED HERE (STRICT MATCH)
    def search_videos(self, channel_id, keyword):
        try:
            res = self.youtube.channels().list(
                part="contentDetails",
                id=channel_id
            ).execute()

            uploads_playlist = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            videos = []
            next_page_token = None
            keyword_lower = keyword.lower()

            pattern = r'\b' + re.escape(keyword_lower) + r'\b'

            while True:
                playlist_res = self.youtube.playlistItems().list(
                    part="snippet",
                    playlistId=uploads_playlist,
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()

                for item in playlist_res.get("items", []):
                    title = item['snippet']['title'].lower()

                    # ✅ STRICT MATCH (FIX)
                    if re.search(pattern, title):
                        videos.append({
                            "id": {"videoId": item['snippet']['resourceId']['videoId']},
                            "snippet": item['snippet']
                        })

                next_page_token = playlist_res.get("nextPageToken")

                if not next_page_token:
                    break

            return videos

        except Exception as e:
            print("ERROR:", e)
            return []

tool = YouTubeTool(API_KEY)

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr
    usage = get_usage(ip)

    if request.method == 'POST':

        url = request.form.get('url', '').strip()
        keyword = request.form['keyword']

        if url == "":
            videos = tool.search_global_videos(keyword)
            channels = tool.search_channels(keyword)
            record_usage(ip)

            return render_template_string(GLOBAL_HTML,
                videos=videos,
                channels=channels,
                vcount=len(videos),
                ccount=len(channels),
                keyword=keyword
            )

        channel_id = tool.resolve_channel(url)

        if not channel_id:
            return "<h2 style='color:red;'>❌ Invalid Input</h2>"

        videos = tool.search_videos(channel_id, keyword)
        record_usage(ip)

        return render_template_string(RESULT_HTML,
            videos=videos,
            count=len(videos),
            keyword=keyword
        )

    return render_template_string(INDEX_HTML, usage=usage)

# ---------------- HTML ----------------
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
<title>YouTube Keyword Tool</title>
<style>
body {
    font-family: Arial;
    background: #0f0f0f;
    color: white;
    text-align: center;
}

.container {
    margin-top: 80px;
}

input {
    padding: 12px;
    width: 300px;
    margin: 10px;
    border-radius: 8px;
    border: none;
}

button {
    padding: 12px 25px;
    background: red;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
}

button:hover {
    background: #cc0000;
}
</style>
</head>

<body>

<div class="container">
<h1>🎬 YouTube Keyword Tool</h1>

<form method="POST">
<input name="url" placeholder="Channel URL / @handle (optional)"><br>
<input name="keyword" placeholder="Enter keyword" required><br>
<button type="submit">Search</button>
</form>

<p>Usage: {{ usage }}</p>
</div>

</body>
</html>
'''

GLOBAL_HTML = '''
<!DOCTYPE html>
<html>
<head>
<style>
body {
    background: #0f0f0f;
    color: white;
    font-family: Arial;
}

.container {
    width: 80%;
    margin: auto;
}

.card {
    background: #1f1f1f;
    padding: 15px;
    margin: 10px 0;
    border-radius: 10px;
    transition: 0.3s;
}

.card:hover {
    transform: scale(1.02);
    background: #2a2a2a;
}

a {
    color: #3ea6ff;
    text-decoration: none;
}
</style>
</head>

<body>

<div class="container">

<h2>🌍 Results for "{{ keyword }}"</h2>

<h3>🎬 Videos ({{ vcount }})</h3>

{% for v in videos %}
<div class="card">
<a href="https://youtube.com/watch?v={{ v.id.videoId }}" target="_blank">
<b>{{ v.snippet.title }}</b>
</a><br>
📺 {{ v.snippet.channelTitle }}
</div>
{% endfor %}

<hr>

<h3>📺 Channels ({{ ccount }})</h3>

{% for ch in channels %}
<div class="card">
<b>{{ ch.title }}</b><br>
<a href="https://youtube.com/channel/{{ ch.channelId }}" target="_blank">Visit Channel</a>
</div>
{% endfor %}

<br><a href="/">⬅ Back</a>

</div>

</body>
</html>
'''

RESULT_HTML = '''
<!DOCTYPE html>
<html>
<head>
<style>
body {
    background: #0f0f0f;
    color: white;
    font-family: Arial;
}

.container {
    width: 80%;
    margin: auto;
}

.card {
    background: #1f1f1f;
    padding: 15px;
    margin: 10px 0;
    border-radius: 10px;
    transition: 0.3s;
}

.card:hover {
    transform: scale(1.02);
    background: #2a2a2a;
}

a {
    color: #3ea6ff;
    text-decoration: none;
}
</style>
</head>

<body>

<div class="container">

<h2>📊 Channel Results</h2>
<h3>🎬 Videos Found: {{ count }}</h3>
<p>Keyword: <b>{{ keyword }}</b></p>

{% for v in videos %}
<div class="card">
<a href="https://youtube.com/watch?v={{ v.id.videoId }}" target="_blank">
<b>{{ v.snippet.title }}</b>
</a>
</div>
{% endfor %}

<br><a href="/">⬅ Back</a>

</div>

</body>
</html>
'''

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)