from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-2024'

# ✅ API from Render ENV
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("❌ API KEY NOT FOUND")

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
        self.youtube = None
        if api_key:
            try:
                self.youtube = googleapiclient.discovery.build(
                    "youtube", "v3", developerKey=api_key
                )
            except Exception as e:
                print("ERROR INIT:", e)

    def is_ready(self):
        return self.youtube is not None

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
            print("ERROR get_channel:", e)
            return None

    def resolve_channel(self, input_text):
        try:
            input_text = input_text.strip()

            # Channel ID
            if input_text.startswith("UC"):
                return input_text

            # Handle (@username)
            if "@" in input_text:
                handle = input_text.split("@")[-1].split("?")[0]
                res = self.youtube.search().list(
                    part="snippet",
                    q=handle,
                    type="channel",
                    maxResults=1
                ).execute()
                return res['items'][0]['snippet']['channelId']

            # Channel URL
            if "youtube.com/channel/" in input_text:
                return input_text.split("channel/")[1].split("/")[0]

            # Video URL
            video_id = self.extract_video_id(input_text)
            if video_id:
                return self.get_channel_from_video(video_id)

            # Keyword → channel
            res = self.youtube.search().list(
                part="snippet",
                q=input_text,
                type="channel",
                maxResults=1
            ).execute()
            return res['items'][0]['snippet']['channelId']

        except Exception as e:
            print("ERROR resolve:", e)
            return None

    # 🔥 GLOBAL SEARCH (KEYWORD ONLY)
    def search_global_videos(self, keyword):
        try:
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

        except Exception as e:
            print("ERROR global:", e)
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
                    "title": item["snippet"]["title"]
                })

            return channels

        except Exception as e:
            print("ERROR channels:", e)
            return []

    # 🔥 CHANNEL SEARCH
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
            print("ERROR channel videos:", e)
            return []

tool = YouTubeTool(API_KEY)

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr
    usage = get_usage(ip)
    remaining = max(0, FREE_SEARCHES_DAY - usage)

    if request.method == 'POST':

        if not tool.is_ready():
            return "<h2 style='color:red;'>❌ API KEY NOT SET</h2>"

        url = request.form.get('url', '').strip()
        keyword = request.form['keyword']

        # ✅ CASE 1: ONLY KEYWORD
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

        # ✅ CASE 2: CHANNEL + KEYWORD
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

<p>Usage: {{ usage }} | Remaining: {{ remaining }}</p>
'''

GLOBAL_HTML = '''
<h2>🌍 Results for "{{ keyword }}"</h2>

<h3>🎬 Videos Found: {{ vcount }}</h3>
{% for v in videos %}
<div>
<a href="https://youtube.com/watch?v={{ v.id.videoId }}" target="_blank">
<b>{{ v.snippet.title }}</b>
</a><br>
📺 {{ v.snippet.channelTitle }}
</div><br>
{% endfor %}

<hr>

<h3>📺 Channels ({{ ccount }})</h3>
{% for ch in channels %}
<div>
<b>{{ ch.title }}</b><br>
<a href="https://youtube.com/channel/{{ ch.channelId }}" target="_blank">Visit</a>
</div>
{% endfor %}

<br><a href="/">Back</a>
'''

RESULT_HTML = '''
<h2>📊 Channel Results</h2>
<h3>🎬 Videos Found: {{ count }}</h3>
<p>Keyword: <b>{{ keyword }}</b></p>

{% for v in videos %}
<div>
<a href="https://youtube.com/watch?v={{ v.id.videoId }}" target="_blank">
<b>{{ v.snippet.title }}</b>
</a>
</div><br>
{% endfor %}

<br><a href="/">Back</a>
'''

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)