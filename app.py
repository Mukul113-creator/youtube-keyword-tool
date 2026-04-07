from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-2024'

# ✅ GET API KEY FROM RENDER ENV
API_KEY = os.getenv("API_KEY")

# LIMITS
GOOGLE_FREE_QUOTA = 10000
SEARCHES_PER_QUERY = 100
FREE_SEARCHES_DAY = GOOGLE_FREE_QUOTA // SEARCHES_PER_QUERY

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
        try:
            res = self.youtube.videos().list(
                part="snippet", id=video_id
            ).execute()
            return res['items'][0]['snippet']['channelId']
        except Exception as e:
            print("ERROR get_channel_from_video:", e)
            return None

    def resolve_channel(self, input_text):
        input_text = input_text.strip()

        # Channel ID
        if input_text.startswith("UC"):
            return input_text

        # Handle (@username)
        if "@" in input_text:
            try:
                handle = input_text.split("@")[-1].split("?")[0]
                res = self.youtube.search().list(
                    part="snippet",
                    q=handle,
                    type="channel",
                    maxResults=1
                ).execute()
                return res['items'][0]['snippet']['channelId']
            except Exception as e:
                print("ERROR handle:", e)
                return None

        # Channel URL
        if "youtube.com/channel/" in input_text:
            return input_text.split("channel/")[1].split("/")[0]

        # Video URL
        video_id = self.extract_video_id(input_text)
        if video_id:
            return self.get_channel_from_video(video_id)

        # Keyword → channel
        try:
            res = self.youtube.search().list(
                part="snippet",
                q=input_text,
                type="channel",
                maxResults=1
            ).execute()
            return res['items'][0]['snippet']['channelId']
        except Exception as e:
            print("ERROR resolve_channel:", e)
            return None

    def search_videos(self, channel_id, keyword):
        try:
            res = self.youtube.search().list(
                part="snippet,id",
                channelId=channel_id,
                q=keyword,
                type="video",
                maxResults=50
            ).execute()

            return res.get('items', [])
        except Exception as e:
            print("ERROR search_videos:", e)
            return []

    def search_global_videos(self, keyword):
        try:
            res = self.youtube.search().list(
                part="snippet,id",
                q=keyword,
                type="video",
                maxResults=25
            ).execute()

            return res.get('items', [])
        except Exception as e:
            print("ERROR global_videos:", e)
            return []

    def search_channels(self, keyword):
        try:
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
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"]
                })

            return channels
        except Exception as e:
            print("ERROR search_channels:", e)
            return []

tool = YouTubeTool(API_KEY)

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr
    usage = get_usage(ip)
    remaining = max(0, FREE_SEARCHES_DAY - usage)

    if request.method == 'POST':

        url = request.form.get('url', '').strip()
        keyword = request.form['keyword']

        # CASE 1: only keyword
        if url == "":
            channels = tool.search_channels(keyword)
            videos = tool.search_global_videos(keyword)
            record_usage(ip)

            return render_template_string(GLOBAL_HTML,
                channels=channels,
                videos=videos,
                keyword=keyword,
                vcount=len(videos),
                ccount=len(channels)
            )

        # CASE 2: channel + keyword
        channel_id = tool.resolve_channel(url)

        if not channel_id:
            return '<h2 style="color:red;">❌ Invalid YouTube Input</h2>'

        videos = tool.search_videos(channel_id, keyword)
        record_usage(ip)

        return render_template_string(RESULTS_HTML,
            videos=videos,
            keyword=keyword,
            count=len(videos)
        )

    return render_template_string(INDEX_HTML,
        usage=usage,
        remaining=remaining
    )

# ---------------- HTML ----------------
INDEX_HTML = '''
<h1>YouTube Keyword Tool</h1>

<form method="POST">
<input name="url" placeholder="Channel URL / @handle / Channel ID (optional)"><br><br>
<input name="keyword" placeholder="Keyword" required><br><br>
<button type="submit">Search</button>
</form>

<p>Daily Usage: {{ usage }} | Remaining: {{ remaining }}</p>
'''

RESULTS_HTML = '''
<h2>🎬 {{ count }} Videos Found</h2>
<p>Keyword: <b>{{ keyword }}</b></p>

{% for video in videos %}
<div>
<a href="https://youtube.com/watch?v={{ video.id.videoId }}" target="_blank">
{{ video.snippet.title }}
</a>
</div>
{% endfor %}

<br><a href="/">Back</a>
'''

GLOBAL_HTML = '''
<h2>🌍 Global Search Results</h2>

<h3>📺 Channels ({{ ccount }})</h3>
{% for ch in channels %}
<div>
<b>{{ ch.title }}</b><br>
<a href="https://youtube.com/channel/{{ ch.channelId }}" target="_blank">Visit</a>
</div>
{% endfor %}

<hr>

<h3>🎬 Videos ({{ vcount }})</h3>
{% for v in videos %}
<div>
<a href="https://youtube.com/watch?v={{ v.id.videoId }}" target="_blank">
{{ v.snippet.title }}
</a>
</div>
{% endfor %}

<br><a href="/">Back</a>
'''

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)