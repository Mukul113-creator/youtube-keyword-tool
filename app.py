from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your-secret-2024'

API_KEY = os.getenv('YOUTUBE_API_KEY')

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

    # Extract video ID
    def extract_video_id(self, url):
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
        return match.group(1) if match else None

    # Get channel from video
    def get_channel_from_video(self, video_id):
        try:
            res = self.youtube.videos().list(
                part="snippet", id=video_id
            ).execute()
            return res['items'][0]['snippet']['channelId']
        except:
            return None

    # 🔥 UNIVERSAL RESOLVER
    def resolve_channel(self, input_text):
        input_text = input_text.strip()

        if "youtube.com/channel/" in input_text:
            return input_text.split("channel/")[1].split("/")[0]

        video_id = self.extract_video_id(input_text)
        if video_id:
            return self.get_channel_from_video(video_id)

        # @handle or channel name
        try:
            res = self.youtube.search().list(
                part="snippet",
                q=input_text,
                type="channel",
                maxResults=1
            ).execute()

            return res['items'][0]['snippet']['channelId']
        except:
            return None

    # 🔍 SEARCH VIDEOS (PAGINATION)
    def search_videos(self, channel_id, keyword):
        try:
            videos = []
            next_page_token = None

            keyword_lower = keyword.lower()
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'

            while True:
                res = self.youtube.search().list(
                    part="snippet,id",
                    channelId=channel_id,
                    q=keyword,
                    type="video",
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()

                items = res.get('items', [])

                for video in items:
                    title = video['snippet']['title'].lower()
                    desc = video['snippet']['description'].lower()

                    if re.search(pattern, title) or re.search(pattern, desc):
                        videos.append(video)

                next_page_token = res.get('nextPageToken')

                if not next_page_token or len(videos) >= 200:
                    break

            return videos

        except Exception as e:
            print("ERROR:", e)
            return []

    # 🆕 SEARCH CHANNELS BY KEYWORD
    def search_channels_by_keyword(self, keyword):
        try:
            channels = []
            next_page_token = None

            while True:
                res = self.youtube.search().list(
                    part="snippet",
                    q=keyword,
                    type="channel",
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()

                for item in res.get("items", []):
                    channels.append({
                        "channelId": item["snippet"]["channelId"],
                        "title": item["snippet"]["title"],
                        "description": item["snippet"]["description"]
                    })

                next_page_token = res.get("nextPageToken")

                if not next_page_token or len(channels) >= 100:
                    break

            return channels

        except Exception as e:
            print("ERROR:", e)
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

        # 🆕 CASE 1: Only keyword → show channels
        if url == "":
            channels = tool.search_channels_by_keyword(keyword)
            record_usage(ip)

            return render_template_string(CHANNELS_HTML,
                channels=channels,
                keyword=keyword,
                count=len(channels)
            )

        # ✅ CASE 2: URL + keyword → show videos
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
<input name="url" placeholder="Channel URL / @handle (optional)"><br><br>
<input name="keyword" placeholder="Keyword" required><br><br>
<button type="submit">Search</button>
</form>

<p>Daily Usage: {{ usage }} | Remaining: {{ remaining }}</p>
'''

RESULTS_HTML = '''
<h2>🎬 {{ count }} Videos Found</h2>
<p>Keyword: <b>{{ keyword }}</b></p>

{% for video in videos %}
<div style="margin-bottom:20px;">
<a href="https://youtube.com/watch?v={{ video.id.videoId }}" target="_blank">
{{ video.snippet.title }}
</a>
</div>
{% endfor %}

<br><a href="/">🔙 Back</a>
'''

CHANNELS_HTML = '''
<h2>📺 {{ count }} Channels Found</h2>
<p>Keyword: <b>{{ keyword }}</b></p>

{% for ch in channels %}
<div style="margin-bottom:20px; padding:10px; border:1px solid #ccc;">
    <h3>{{ ch.title }}</h3>
    <p>{{ ch.description }}</p>
    <a href="https://youtube.com/channel/{{ ch.channelId }}" target="_blank">
        Visit Channel
    </a>
</div>
{% endfor %}

<br><a href="/">🔙 Back</a>
'''

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)